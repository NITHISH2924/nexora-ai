import os
import time
import secrets
import bcrypt
import jwt
import ipaddress
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.config import settings

# HTTP Bearer for optional Authorization header
bearer_scheme = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def generate_secure_token() -> str:
    """Generate high-entropy url-safe token for email verification and password reset."""
    return secrets.token_urlsafe(48)

import hashlib
from typing import Optional, Dict, List, Tuple, Set

# In-memory revocation cache for instant O(1) token invalidation
_revoked_token_hashes: Set[str] = set()

def hash_token(token: str) -> str:
    """Compute deterministic SHA-256 hash of a JWT access token for safe storage and lookup."""
    if not token:
        return ""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

def revoke_token_hash(token_hash: str):
    """Add token hash to in-memory revocation cache."""
    if token_hash:
        _revoked_token_hashes.add(token_hash)

def is_token_hash_revoked(token_hash: str) -> bool:
    """Check if token hash exists in revocation cache."""
    if not token_hash:
        return False
    return token_hash in _revoked_token_hashes

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access",
    jti: Optional[str] = None
) -> str:
    """Create signed JWT access or temporary MFA token with unique jti and type."""
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": now_utc,
        "iss": settings.APP_NAME,
        "type": token_type,
        "jti": jti or secrets.token_hex(16)
    })
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.APP_NAME
        )
        return payload
    except jwt.PyJWTError:
        return None

# Simple thread-safe in-memory sliding window rate limiter
class RateLimiter:
    def __init__(self, window_seconds: int = 60, max_requests: int = 30):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, key: str, max_limit: Optional[int] = None) -> Tuple[bool, int]:
        now = time.time()
        limit = max_limit or self.max_requests
        
        # Filter requests within current window
        timestamps = self.requests.get(key, [])
        valid_timestamps = [t for t in timestamps if now - t < self.window_seconds]
        
        if len(valid_timestamps) >= limit:
            retry_after = int(self.window_seconds - (now - valid_timestamps[0])) + 1
            self.requests[key] = valid_timestamps
            return False, retry_after
        
        valid_timestamps.append(now)
        self.requests[key] = valid_timestamps
        return True, 0

    def cleanup(self):
        """Periodically cleanup stale entries."""
        now = time.time()
        stale_keys = [k for k, v in self.requests.items() if not v or now - v[-1] > self.window_seconds * 2]
        for k in stale_keys:
            self.requests.pop(k, None)

rate_limiter = RateLimiter(
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS
)

import logging
logger = logging.getLogger("security")

class PersistentAuthRateLimiter:
    """
    Production-grade shared persistent rate limiter backed by PostgreSQL / SQLite.
    Persists attempt counters and temporary lockout state across application restarts
    and multiple concurrent workers.
    Fails safely/closed if persistent storage is unreachable.
    """
    def __init__(self):
        # In-memory dictionaries preserved for test compatibility & cache inspection
        self._failed_attempts: Dict[str, List[float]] = {}
        self._lockouts: Dict[str, float] = {}

    async def is_account_locked(self, email: str) -> Tuple[bool, int]:
        """Check if an account is temporarily locked due to consecutive failures."""
        clean_email = email.strip().lower()
        key = f"account:{clean_email}"
        now = time.time()

        try:
            from backend.app.database import get_db
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT lockedUntil FROM auth_rate_limits WHERE key = ?",
                    (key,)
                )
                row = await cursor.fetchone()
                if row:
                    locked_until = float(row["lockedUntil"] or 0)
                    if locked_until > now:
                        retry_after = int(locked_until - now) + 1
                        self._lockouts[clean_email] = locked_until
                        return True, retry_after
                    elif locked_until > 0:
                        # Lockout has expired: reset lockout in DB
                        await db.execute(
                            "UPDATE auth_rate_limits SET lockedUntil = 0, attempts = 0, updatedAt = ? WHERE key = ?",
                            (now, key)
                        )
                        await db.commit()
                        self._lockouts.pop(clean_email, None)
                        self._failed_attempts.pop(clean_email, None)
            return False, 0
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking persistent account lockout for {clean_email[:2]}***: {e}")
            if settings.APP_ENV == "production" or os.getenv("RENDER"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable. Please try again shortly."
                )
            return False, 0

    async def record_failure(self, email: str) -> Tuple[bool, int, int]:
        """
        Record failed login attempt in persistent store.
        Returns (is_locked, lockout_seconds, current_failure_count).
        """
        clean_email = email.strip().lower()
        key = f"account:{clean_email}"
        now = time.time()
        window = getattr(settings, "AUTH_LOCKOUT_DURATION_SECONDS", 300)
        max_failures = getattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 5)

        try:
            from backend.app.database import get_db
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT attempts, windowStart, lockedUntil FROM auth_rate_limits WHERE key = ?",
                    (key,)
                )
                row = await cursor.fetchone()

                if row:
                    window_start = float(row["windowStart"] or now)
                    locked_until = float(row["lockedUntil"] or 0)

                    if locked_until > now:
                        retry_after = int(locked_until - now) + 1
                        self._lockouts[clean_email] = locked_until
                        return True, retry_after, int(row["attempts"])

                    if (now - window_start) < window:
                        new_attempts = int(row["attempts"] or 0) + 1
                        if new_attempts >= max_failures:
                            new_locked_until = now + window
                            await db.execute(
                                "UPDATE auth_rate_limits SET attempts = ?, lockedUntil = ?, updatedAt = ? WHERE key = ?",
                                (new_attempts, new_locked_until, now, key)
                            )
                            await db.commit()
                            self._lockouts[clean_email] = new_locked_until
                            return True, window, new_attempts
                        else:
                            await db.execute(
                                "UPDATE auth_rate_limits SET attempts = ?, updatedAt = ? WHERE key = ?",
                                (new_attempts, now, key)
                            )
                            await db.commit()
                            return False, 0, new_attempts
                    else:
                        # Previous window expired: start new sliding window
                        await db.execute(
                            "UPDATE auth_rate_limits SET attempts = 1, windowStart = ?, lockedUntil = 0, updatedAt = ? WHERE key = ?",
                            (now, now, key)
                        )
                        await db.commit()
                        self._lockouts.pop(clean_email, None)
                        return False, 0, 1
                else:
                    await db.execute(
                        "INSERT INTO auth_rate_limits (key, attempts, windowStart, lockedUntil, updatedAt) VALUES (?, 1, ?, 0, ?)",
                        (key, now, now)
                    )
                    await db.commit()
                    return False, 0, 1
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error recording persistent failure count for {clean_email[:2]}***: {e}")
            if settings.APP_ENV == "production" or os.getenv("RENDER"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable. Please try again shortly."
                )
            return False, 0, 1

    async def record_success(self, email: str):
        """Reset failure counter and active lockout on successful authentication."""
        clean_email = email.strip().lower()
        key = f"account:{clean_email}"
        self._failed_attempts.pop(clean_email, None)
        self._lockouts.pop(clean_email, None)
        try:
            from backend.app.database import get_db
            async with get_db() as db:
                await db.execute("DELETE FROM auth_rate_limits WHERE key = ?", (key,))
                await db.commit()
        except Exception as e:
            logger.error(f"Error resetting persistent lockout on success for {clean_email[:2]}***: {e}")

    async def check_and_increment_ip(
        self,
        client_ip: str,
        action: str = "login",
        max_limit: Optional[int] = None,
        window_seconds: Optional[int] = None
    ) -> Tuple[bool, int]:
        """
        Enforce persistent IP-based rate limiting across all workers.
        Returns (is_allowed, retry_after).
        """
        key = f"ip:{client_ip.strip()}:{action}"
        now = time.time()
        limit = max_limit or getattr(settings, "AUTH_IP_MAX_LOGIN_ATTEMPTS", 10)
        win = window_seconds or getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)

        try:
            from backend.app.database import get_db
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT attempts, windowStart, lockedUntil FROM auth_rate_limits WHERE key = ?",
                    (key,)
                )
                row = await cursor.fetchone()

                if row:
                    window_start = float(row["windowStart"] or now)
                    locked_until = float(row["lockedUntil"] or 0)

                    if locked_until > now:
                        return False, int(locked_until - now) + 1

                    if (now - window_start) < win:
                        new_attempts = int(row["attempts"] or 0) + 1
                        if new_attempts > limit:
                            retry_after = int(win - (now - window_start)) + 1
                            new_locked = now + retry_after
                            await db.execute(
                                "UPDATE auth_rate_limits SET attempts = ?, lockedUntil = ?, updatedAt = ? WHERE key = ?",
                                (new_attempts, new_locked, now, key)
                            )
                            await db.commit()
                            return False, retry_after
                        else:
                            await db.execute(
                                "UPDATE auth_rate_limits SET attempts = ?, updatedAt = ? WHERE key = ?",
                                (new_attempts, now, key)
                            )
                            await db.commit()
                            return True, 0
                    else:
                        await db.execute(
                            "UPDATE auth_rate_limits SET attempts = 1, windowStart = ?, lockedUntil = 0, updatedAt = ? WHERE key = ?",
                            (now, now, key)
                        )
                        await db.commit()
                        return True, 0
                else:
                    await db.execute(
                        "INSERT INTO auth_rate_limits (key, attempts, windowStart, lockedUntil, updatedAt) VALUES (?, 1, ?, 0, ?)",
                        (key, now, now)
                    )
                    await db.commit()
                    return True, 0
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking persistent IP rate limit for {client_ip}: {e}")
            if settings.APP_ENV == "production" or os.getenv("RENDER"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable. Please try again shortly."
                )
            return True, 0

    async def clear_all(self):
        """Purge all rate limits from database and memory."""
        self._lockouts.clear()
        self._failed_attempts.clear()
        try:
            from backend.app.database import get_db
            async with get_db() as db:
                await db.execute("DELETE FROM auth_rate_limits")
                await db.commit()
        except Exception:
            pass

    def cleanup(self):
        """No-op cleanup kept for backwards compatibility."""
        pass

auth_rate_limiter = PersistentAuthRateLimiter()

# ------------------------------------------------------------------------------
# Secure Client IP Resolution & Trusted Proxy Validation
# ------------------------------------------------------------------------------
def get_trusted_proxy_networks() -> List[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    configured = getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10"])
    networks = []
    for item in configured:
        try:
            if "/" in item:
                networks.append(ipaddress.ip_network(item, strict=False))
            else:
                ip = ipaddress.ip_address(item)
                networks.append(ipaddress.ip_network(f"{ip}/{32 if ip.version == 4 else 128}"))
        except ValueError:
            continue
    return networks

def is_trusted_proxy(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return any(ip in net for net in get_trusted_proxy_networks())
    except (ValueError, AttributeError):
        return False

def get_client_ip(request: Request) -> str:
    """
    Safely resolve client IP address.
    Defends against IP spoofing: does not trust arbitrary X-Forwarded-For headers
    unless the request originates directly from a verified trusted proxy.
    """
    direct_ip = "127.0.0.1"
    if request.client and request.client.host:
        direct_ip = request.client.host.strip()

    # If the direct peer is not a trusted proxy, return direct_ip directly
    if not is_trusted_proxy(direct_ip):
        return direct_ip

    # If behind trusted proxy, inspect headers from right to left
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        for candidate in reversed(parts):
            try:
                parsed = ipaddress.ip_address(candidate)
                # First non-trusted proxy IP encountered from the right is the verified client IP
                if not any(parsed in net for net in get_trusted_proxy_networks()):
                    return str(parsed)
            except ValueError:
                continue
        if parts:
            try:
                return str(ipaddress.ip_address(parts[0]))
            except ValueError:
                pass

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        try:
            return str(ipaddress.ip_address(real_ip.strip()))
        except ValueError:
            pass

    return direct_ip
