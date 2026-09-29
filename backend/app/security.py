import time
import secrets
import bcrypt
import jwt
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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.APP_NAME
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
