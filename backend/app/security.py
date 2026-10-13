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

class AuthRateLimiter:
    """
    Two-tier brute-force defense limiter:
    - Account-level consecutive failure lockout
    - IP-level rate limiting
    """
    def __init__(self):
        self._failed_attempts: Dict[str, List[float]] = {}
        self._lockouts: Dict[str, float] = {}

    def is_account_locked(self, email: str) -> Tuple[bool, int]:
        clean_email = email.strip().lower()
        now = time.time()
        
        # Check active lockout
        lockout_expiry = self._lockouts.get(clean_email, 0)
        if lockout_expiry > now:
            return True, int(lockout_expiry - now) + 1
        elif clean_email in self._lockouts:
            self._lockouts.pop(clean_email, None)
            self._failed_attempts.pop(clean_email, None)

        # Check consecutive failures within window
        window = getattr(settings, "AUTH_LOCKOUT_DURATION_SECONDS", 300)
        max_failures = getattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 5)
        failures = self._failed_attempts.get(clean_email, [])
        valid_failures = [t for t in failures if now - t < window]
        self._failed_attempts[clean_email] = valid_failures

        if len(valid_failures) >= max_failures:
            # Lock out account
            self._lockouts[clean_email] = now + window
            return True, window

        return False, 0

    def record_failure(self, email: str) -> int:
        clean_email = email.strip().lower()
        now = time.time()
        window = getattr(settings, "AUTH_LOCKOUT_DURATION_SECONDS", 300)
        max_failures = getattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 5)

        failures = self._failed_attempts.get(clean_email, [])
        valid_failures = [t for t in failures if now - t < window]
        valid_failures.append(now)
        self._failed_attempts[clean_email] = valid_failures

        if len(valid_failures) >= max_failures:
            self._lockouts[clean_email] = now + window

        return len(valid_failures)

    def record_success(self, email: str):
        clean_email = email.strip().lower()
        self._failed_attempts.pop(clean_email, None)
        self._lockouts.pop(clean_email, None)

    def cleanup(self):
        now = time.time()
        expired_locks = [k for k, v in self._lockouts.items() if v <= now]
        for k in expired_locks:
            self._lockouts.pop(k, None)
        window = getattr(settings, "AUTH_LOCKOUT_DURATION_SECONDS", 300)
        stale_accts = [k for k, v in self._failed_attempts.items() if not v or (now - v[-1] > window * 2)]
        for k in stale_accts:
            self._failed_attempts.pop(k, None)

auth_rate_limiter = AuthRateLimiter()

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
