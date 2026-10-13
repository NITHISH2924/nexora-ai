import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import aiosqlite
from fastapi import HTTPException, status
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.security import (
    hash_password,
    verify_password,
    generate_secure_token,
    create_access_token,
    decode_access_token,
    hash_token,
    revoke_token_hash,
    is_token_hash_revoked,
    auth_rate_limiter
)
from backend.app.models import (
    UserRegisterRequest,
    UserResponse,
    UserLoginRequest,
    ResetPasswordRequest,
    ChangePasswordRequest
)
from backend.app.services.email_service import email_service
from backend.app.services.mfa_service import mfa_service

def row_to_user_dict(row: Any) -> dict:
    """Convert db row or dict to safe user dict for UserResponse."""
    keys = row.keys() if hasattr(row, "keys") else dict(row).keys()
    full_name = row["fullName"] if "fullName" in keys else (row["displayName"] if "displayName" in keys else None)
    return {
        "userId": row["userId"],
        "email": row["email"],
        "fullName": full_name,
        "role": row["role"],
        "accountCreatedAt": row["accountCreatedAt"],
        "lastLoginAt": row["lastLoginAt"],
        "loginCount": row["loginCount"],
        "accountStatus": row["accountStatus"],
        "emailVerified": bool(row["emailVerified"]),
        "mfaEnabled": bool(row["mfaEnabled"]) if "mfaEnabled" in keys else False
    }

class UserService:
    @staticmethod
    async def log_activity(db: Any, user_id: str, action: str, details: Optional[str] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        if not user_id or user_id in ("anonymous", "system"):
            return
        now = datetime.now(timezone.utc).isoformat()
        try:
            await db.execute(
                "INSERT INTO audit_logs (userId, action, details, ipAddress, userAgent, createdAt) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, action, details, ip_address, user_agent, now)
            )
            await db.commit()
        except Exception:
            pass

    @classmethod
    async def create_session(cls, db: Any, user_id: str, token: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None, expires_delta: Optional[timedelta] = None):
        """Register active session in database."""
        session_id = str(uuid.uuid4())
        token_hash = hash_token(token)
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        if expires_delta:
            exp_str = (now_dt + expires_delta).isoformat()
        else:
            exp_str = (now_dt + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).isoformat()
        
        await db.execute("""
        INSERT INTO active_sessions (
            sessionId, userId, tokenHash, ipAddress, userAgent,
            createdAt, lastSeenAt, expiresAt, isRevoked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (session_id, user_id, token_hash, ip_address, user_agent, now_str, now_str, exp_str))
        await db.commit()

    @classmethod
    async def revoke_session(cls, token: str, user_id: str, reason: str = "USER_LOGOUT", ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Immediately invalidate a specific session token."""
        token_hash = hash_token(token)
        revoke_token_hash(token_hash)
        now = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            await db.execute(
                "UPDATE active_sessions SET isRevoked = 1, revokedAt = ?, revocationReason = ? WHERE tokenHash = ?",
                (now, reason, token_hash)
            )
            await db.commit()
            await cls.log_activity(db, user_id, "LOGOUT", f"Session revoked: {reason}", ip_address, user_agent)

    @classmethod
    async def revoke_all_user_sessions(cls, user_id: str, reason: str = "SECURITY_RESET", ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Invalidate all active sessions for a user (password change, suspension, admin reset)."""
        now = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            await db.execute(
                "UPDATE users SET tokenRevocationTimestamp = ? WHERE userId = ?",
                (now, user_id)
            )
            await db.execute(
                "UPDATE active_sessions SET isRevoked = 1, revokedAt = ?, revocationReason = ? WHERE userId = ?",
                (now, reason, user_id)
            )
            await db.commit()
            await cls.log_activity(db, user_id, "SESSIONS_REVOKED", f"All active sessions invalidated: {reason}", ip_address, user_agent)

    @classmethod
    async def validate_session(cls, user_id: str, token_hash: str, token_iat_timestamp: Optional[Any] = None) -> bool:
        """Validate whether token is active, unexpired, and unrevoked."""
        if is_token_hash_revoked(token_hash):
            return False

        async with get_db() as db:
            async with db.execute("SELECT accountStatus, tokenRevocationTimestamp FROM users WHERE userId = ?", (user_id,)) as cursor:
                raw_user = await cursor.fetchone()
                if not raw_user:
                    return False
                user_row = dict(raw_user)
                if user_row.get("accountStatus") == "SUSPENDED":
                    return False
                rev_ts = user_row.get("tokenRevocationTimestamp")
                if rev_ts and token_iat_timestamp:
                    try:
                        if isinstance(token_iat_timestamp, (int, float)):
                            token_sec = int(token_iat_timestamp)
                        elif isinstance(token_iat_timestamp, datetime):
                            token_sec = int(token_iat_timestamp.timestamp())
                        else:
                            token_sec = int(datetime.fromisoformat(str(token_iat_timestamp)).timestamp())
                        
                        rev_sec = int(datetime.fromisoformat(rev_ts).timestamp())
                        if token_sec < rev_sec:
                            return False
                    except Exception:
                        pass

            try:
                async with db.execute("SELECT isRevoked, expiresAt FROM active_sessions WHERE tokenHash = ?", (token_hash,)) as cursor:
                    raw_sess = await cursor.fetchone()
                    if raw_sess:
                        sess = dict(raw_sess)
                        if sess.get("isRevoked") == 1:
                            return False
                        if sess.get("expiresAt"):
                            try:
                                if datetime.fromisoformat(sess["expiresAt"]) < datetime.now(timezone.utc):
                                    return False
                            except Exception:
                                pass
            except Exception:
                pass

        return True

    @classmethod
    async def setup_mfa(cls, user_id: str) -> dict:
        """Generate new provisional TOTP secret and recovery codes for enrollment."""
        user = await cls.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        secret = mfa_service.generate_mfa_secret()
        uri = mfa_service.get_totp_uri(secret, user["email"])
        plain_codes, _ = mfa_service.generate_recovery_codes(count=8)
        return {
            "secret": secret,
            "otpauthUri": uri,
            "recoveryCodes": plain_codes
        }

    @classmethod
    async def enable_mfa(cls, user_id: str, secret: str, code: str, recovery_codes: List[str], ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        """Verify code against provisional secret and activate MFA on user account."""
        if not mfa_service.verify_totp_code(secret, code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code. Please check your authenticator app.")
        
        hashed_codes = [mfa_service._hash_code(c) for c in recovery_codes]
        codes_json = json.dumps(hashed_codes)

        async with get_db() as db:
            await db.execute(
                "UPDATE users SET mfaEnabled = 1, mfaSecret = ?, mfaRecoveryCodes = ? WHERE userId = ?",
                (secret, codes_json, user_id)
            )
            await db.commit()
            await cls.log_activity(db, user_id, "MFA_ENABLED", "Two-factor authentication enrolled and enabled", ip_address, user_agent)
        return True

    @classmethod
    async def disable_mfa(cls, user_id: str, current_password: str, code: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        """Disable MFA after verifying current password and valid TOTP code."""
        user = await cls.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        if not verify_password(current_password, user["passwordHash"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        
        secret = user.get("mfaSecret", "")
        if not mfa_service.verify_totp_code(secret, code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid two-factor authentication code")

        async with get_db() as db:
            await db.execute(
                "UPDATE users SET mfaEnabled = 0, mfaSecret = NULL, mfaRecoveryCodes = NULL WHERE userId = ?",
                (user_id,)
            )
            await db.commit()
            await cls.log_activity(db, user_id, "MFA_DISABLED", "Two-factor authentication disabled", ip_address, user_agent)
        return True

    @classmethod
    async def verify_mfa_login(cls, mfa_session_token: str, code: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> tuple[dict, str]:
        """Verify TOTP code or backup recovery code during MFA login."""
        payload = decode_access_token(mfa_session_token)
        if not payload or payload.get("type") != "mfa_temp" or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired two-factor authentication session"
            )
        
        user_id = payload["sub"]
        user = await cls.get_user_by_id(user_id)
        if not user or user["accountStatus"] == "SUSPENDED":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or suspended"
            )

        secret = user.get("mfaSecret", "")
        totp_valid = mfa_service.verify_totp_code(secret, code)
        recovery_valid = False
        remaining_recovery_json = None

        if not totp_valid and user.get("mfaRecoveryCodes"):
            try:
                stored_hashes = json.loads(user["mfaRecoveryCodes"])
                recovery_valid, rem_hashes = mfa_service.verify_and_consume_recovery_code(stored_hashes, code)
                if recovery_valid:
                    remaining_recovery_json = json.dumps(rem_hashes)
            except Exception:
                pass

        if not totp_valid and not recovery_valid:
            async with get_db() as db:
                await cls.log_activity(db, user_id, "MFA_FAILED", "Invalid TOTP code or recovery code submitted", ip_address, user_agent)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid two-factor authentication code or recovery code"
            )

        now = datetime.now(timezone.utc).isoformat()
        new_count = user["loginCount"] + 1
        expire_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_payload = {
            "sub": user["userId"],
            "email": user["email"],
            "role": user["role"]
        }
        token = create_access_token(token_payload, expires_delta=expire_delta)

        async with get_db() as db:
            if remaining_recovery_json is not None:
                await db.execute(
                    "UPDATE users SET lastLoginAt = ?, loginCount = ?, mfaRecoveryCodes = ? WHERE userId = ?",
                    (now, new_count, remaining_recovery_json, user["userId"])
                )
            else:
                await db.execute(
                    "UPDATE users SET lastLoginAt = ?, loginCount = ? WHERE userId = ?",
                    (now, new_count, user["userId"])
                )
            await cls.create_session(db, user["userId"], token, ip_address, user_agent, expires_delta=expire_delta)
            await db.commit()
            action_desc = "Successful login via backup recovery code" if recovery_valid else "Successful login via TOTP MFA"
            await cls.log_activity(db, user["userId"], "LOGIN_MFA_SUCCESS", action_desc, ip_address, user_agent)

        user_profile = {
            "userId": user["userId"],
            "email": user["email"],
            "role": user["role"],
            "accountCreatedAt": user["accountCreatedAt"],
            "lastLoginAt": now,
            "loginCount": new_count,
            "accountStatus": user["accountStatus"],
            "emailVerified": bool(user["emailVerified"]),
            "mfaEnabled": True,
            "mfaRequired": False
        }
        return user_profile, token

    @classmethod
    async def get_user_by_email(cls, email: str) -> Optional[dict]:
        clean_email = email.strip().lower()
        async with get_db() as db:
            async with db.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (clean_email,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
        return None

    @classmethod
    async def get_user_by_id(cls, user_id: str) -> Optional[dict]:
        async with get_db() as db:
            async with db.execute("""
            SELECT u.*, p.displayName, p.displayName as fullName
            FROM users u
            LEFT JOIN user_preferences p ON u.userId = p.userId
            WHERE u.userId = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
        return None

    @classmethod
    async def register_user(cls, data: UserRegisterRequest, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> tuple[dict, str]:
        clean_email = data.email.strip().lower()
        existing = await cls.get_user_by_email(clean_email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists"
            )

        # Server-side Leadership Role Assignment check
        if clean_email == settings.OWNER_EMAIL:
            role = "OWNER"
        elif clean_email == settings.CEO_EMAIL:
            role = "CEO"
        else:
            role = "USER"
        
        user_id = str(uuid.uuid4())
        hashed = hash_password(data.password)
        now_dt = datetime.now(timezone.utc)
        created_at = now_dt.isoformat()
        full_name = getattr(data, "fullName", None)
        if full_name:
            full_name = full_name.strip()
        
        # Email verification token valid for 24 hours
        verify_token = generate_secure_token()
        verify_expires = (now_dt + timedelta(hours=24)).isoformat()
        
        # Default accountStatus is ACTIVE so users can sign in immediately while verification email is sent
        account_status = "ACTIVE"
        email_verified = 1 if role in ("OWNER", "CEO") else 0

        # Generate JWT session token
        token_payload = {
            "sub": user_id,
            "email": clean_email,
            "role": role
        }
        token = create_access_token(token_payload)

        async with get_db() as db:
            await db.execute("""
            INSERT INTO users (
                userId, email, passwordHash, role, accountCreatedAt, lastLoginAt,
                loginCount, accountStatus, emailVerified,
                emailVerificationToken, emailVerificationTokenExpires
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, clean_email, hashed, role, created_at, created_at,
                1, account_status, email_verified,
                verify_token if not email_verified else None,
                verify_expires if not email_verified else None
            ))
            if full_name:
                await db.execute("""
                INSERT INTO user_preferences (userId, displayName, updatedAt)
                VALUES (?, ?, ?)
                """, (user_id, full_name, created_at))
            await cls.create_session(db, user_id, token, ip_address, user_agent)
            await db.commit()
            await cls.log_activity(db, user_id, "REGISTER", f"Account created with role {role}", ip_address, user_agent)

        # Dispatch verification email
        if not email_verified:
            email_service.send_verification_email(clean_email, verify_token)
        
        user_profile = {
            "userId": user_id,
            "email": clean_email,
            "fullName": full_name,
            "role": role,
            "accountCreatedAt": created_at,
            "lastLoginAt": created_at,
            "loginCount": 1,
            "accountStatus": account_status,
            "emailVerified": bool(email_verified),
            "mfaEnabled": False
        }
        return user_profile, token

    @classmethod
    async def login_user(cls, data: UserLoginRequest, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> tuple[dict, str]:
        clean_email = data.email.strip().lower()

        # 1. Check account-level lockout
        locked, retry_after = auth_rate_limiter.is_account_locked(clean_email)
        if locked:
            async with get_db() as db:
                await cls.log_activity(
                    db,
                    "system",
                    "LOGIN_LOCKED",
                    f"Blocked login attempt on locked account ({clean_email[:2]}***)",
                    ip_address,
                    user_agent
                )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Account temporarily locked for {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)}
            )

        user = await cls.get_user_by_email(clean_email)
        
        # 2. Verify credentials
        if not user or not verify_password(data.password, user["passwordHash"]):
            failure_count = auth_rate_limiter.record_failure(clean_email)
            async with get_db() as db:
                uid = user["userId"] if user else "anonymous"
                await cls.log_activity(
                    db,
                    uid,
                    "LOGIN_FAILED",
                    f"Failed login attempt for {clean_email[:2]}*** (consecutive failure {failure_count})",
                    ip_address,
                    user_agent
                )
            now_locked, lock_seconds = auth_rate_limiter.is_account_locked(clean_email)
            if now_locked:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Account temporarily locked for {lock_seconds} seconds.",
                    headers={"Retry-After": str(lock_seconds)}
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # 3. Successful password verification
        auth_rate_limiter.record_success(clean_email)

        # 4. Check account suspension
        if user["accountStatus"] == "SUSPENDED":
            async with get_db() as db:
                await cls.log_activity(db, user["userId"], "LOGIN_REJECTED", "Login attempted on suspended account", ip_address, user_agent)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been suspended. Please contact support."
            )

        # 5. Check if MFA challenge is required
        if user.get("mfaEnabled"):
            mfa_payload = {
                "sub": user["userId"],
                "email": user["email"],
                "role": user["role"],
                "type": "mfa_temp"
            }
            mfa_temp_token = create_access_token(
                mfa_payload,
                expires_delta=timedelta(minutes=getattr(settings, "MFA_TEMP_TOKEN_EXPIRE_MINUTES", 5)),
                token_type="mfa_temp"
            )
            async with get_db() as db:
                await cls.log_activity(db, user["userId"], "LOGIN_MFA_CHALLENGE", "MFA verification challenge presented", ip_address, user_agent)
            return {"mfaRequired": True, "userId": user["userId"]}, mfa_temp_token

        # 6. Standard login without MFA
        now = datetime.now(timezone.utc).isoformat()
        new_count = user["loginCount"] + 1

        # Calculate expiration
        expire_delta = timedelta(days=30) if data.rememberMe else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        token_payload = {
            "sub": user["userId"],
            "email": user["email"],
            "role": user["role"]
        }
        token = create_access_token(token_payload, expires_delta=expire_delta)

        async with get_db() as db:
            await db.execute(
                "UPDATE users SET lastLoginAt = ?, loginCount = ? WHERE userId = ?",
                (now, new_count, user["userId"])
            )
            await cls.create_session(db, user["userId"], token, ip_address, user_agent, expires_delta=expire_delta)
            await db.commit()
            await cls.log_activity(db, user["userId"], "LOGIN", "Successful login", ip_address, user_agent)

        user_profile = {
            "userId": user["userId"],
            "email": user["email"],
            "role": user["role"],
            "accountCreatedAt": user["accountCreatedAt"],
            "lastLoginAt": now,
            "loginCount": new_count,
            "accountStatus": user["accountStatus"],
            "emailVerified": bool(user["emailVerified"]),
            "mfaEnabled": False,
            "mfaRequired": False
        }
        return user_profile, token

    @classmethod
    async def request_password_reset(cls, email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        clean_email = email.strip().lower()
        user = await cls.get_user_by_email(clean_email)
        
        # We always return True to prevent user enumeration attacks
        if not user:
            return True

        token = generate_secure_token()
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        async with get_db() as db:
            await db.execute(
                "UPDATE users SET passwordResetToken = ?, passwordResetTokenExpires = ? WHERE userId = ?",
                (token, expires, user["userId"])
            )
            await db.commit()
            await cls.log_activity(db, user["userId"], "PASSWORD_RESET_REQUESTED", "Reset link generated", ip_address, user_agent)

        email_service.send_password_reset_email(clean_email, token)
        return True

    @classmethod
    async def reset_password(cls, data: ResetPasswordRequest, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        now_dt = datetime.now(timezone.utc)
        async with get_db() as db:
            async with db.execute("SELECT * FROM users WHERE passwordResetToken = ?", (data.token,)) as cursor:
                user = await cursor.fetchone()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired password reset token"
                    )

                expires_str = user["passwordResetTokenExpires"]
                if not expires_str or datetime.fromisoformat(expires_str) < now_dt:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Password reset token has expired. Please request a new one."
                    )

                new_hash = hash_password(data.newPassword)
                await db.execute(
                    "UPDATE users SET passwordHash = ?, passwordResetToken = NULL, passwordResetTokenExpires = NULL WHERE userId = ?",
                    (new_hash, user["userId"])
                )
                await db.commit()
                await cls.revoke_all_user_sessions(user["userId"], reason="PASSWORD_RESET", ip_address=ip_address, user_agent=user_agent)
                await cls.log_activity(db, user["userId"], "PASSWORD_RESET_SUCCESS", "Password updated successfully", ip_address, user_agent)
                return True

    @classmethod
    async def verify_email(cls, token: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        now_dt = datetime.now(timezone.utc)
        async with get_db() as db:
            async with db.execute("SELECT * FROM users WHERE emailVerificationToken = ?", (token,)) as cursor:
                user = await cursor.fetchone()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid verification link or email already verified"
                    )

                expires_str = user["emailVerificationTokenExpires"]
                if expires_str and datetime.fromisoformat(expires_str) < now_dt:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Verification link has expired. Please request a new verification email."
                    )

                await db.execute(
                    "UPDATE users SET emailVerified = 1, emailVerificationToken = NULL, emailVerificationTokenExpires = NULL WHERE userId = ?",
                    (user["userId"],)
                )
                await db.commit()
                await cls.log_activity(db, user["userId"], "EMAIL_VERIFIED", "Email address verified", ip_address, user_agent)
                return True

    @classmethod
    async def resend_verification(cls, email: str) -> bool:
        clean_email = email.strip().lower()
        user = await cls.get_user_by_email(clean_email)
        if not user or user["emailVerified"]:
            return True

        token = generate_secure_token()
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

        async with get_db() as db:
            await db.execute(
                "UPDATE users SET emailVerificationToken = ?, emailVerificationTokenExpires = ? WHERE userId = ?",
                (token, expires, user["userId"])
            )
            await db.commit()

        email_service.send_verification_email(clean_email, token)
        return True

    @classmethod
    async def change_password(cls, user_id: str, data: ChangePasswordRequest, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        user = await cls.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not verify_password(data.currentPassword, user["passwordHash"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

        new_hash = hash_password(data.newPassword)
        async with get_db() as db:
            await db.execute("UPDATE users SET passwordHash = ? WHERE userId = ?", (new_hash, user_id))
            await db.commit()
            await cls.revoke_all_user_sessions(user_id, reason="PASSWORD_CHANGED", ip_address=ip_address, user_agent=user_agent)
            await cls.log_activity(db, user_id, "PASSWORD_CHANGED", "Password changed from user settings", ip_address, user_agent)
            return True

    @classmethod
    async def get_user_activity(cls, user_id: str, limit: int = 20) -> List[dict]:
        async with get_db() as db:
            async with db.execute(
                "SELECT id, action, details, ipAddress, userAgent, createdAt FROM audit_logs WHERE userId = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @classmethod
    async def get_all_users_admin(cls, search: Optional[str] = None, role_filter: Optional[str] = None, status_filter: Optional[str] = None) -> List[dict]:
        query = """
        SELECT u.userId, u.email, u.role, u.accountCreatedAt, u.lastLoginAt, u.loginCount, u.accountStatus, u.emailVerified, p.displayName as fullName
        FROM users u
        LEFT JOIN user_preferences p ON u.userId = p.userId
        WHERE 1=1
        """
        params = []
        if search and search.strip():
            query += " AND u.email LIKE ?"
            params.append(f"%{search.strip()}%")
        if role_filter and role_filter.strip():
            query += " AND u.role = ?"
            params.append(role_filter.strip().upper())
        if status_filter and status_filter.strip():
            query += " AND u.accountStatus = ?"
            params.append(status_filter.strip().upper())
        query += " ORDER BY u.accountCreatedAt DESC"

        async with get_db() as db:
            async with db.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [row_to_user_dict(r) for r in rows]

    @classmethod
    async def update_user_status_admin(cls, target_user_id: str, new_status: str, admin_user_id: str) -> dict:
        user = await cls.get_user_by_id(target_user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        if user["userId"] == admin_user_id and new_status == "SUSPENDED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owners cannot suspend their own account")

        async with get_db() as db:
            await db.execute("UPDATE users SET accountStatus = ? WHERE userId = ?", (new_status, target_user_id))
            await db.commit()
            if new_status == "SUSPENDED":
                await cls.revoke_all_user_sessions(target_user_id, reason="ACCOUNT_SUSPENDED")
            await cls.log_activity(db, admin_user_id, "ADMIN_STATUS_UPDATE", f"Changed status of {user['email']} to {new_status}")
            
        updated = await cls.get_user_by_id(target_user_id)
        return row_to_user_dict(updated)

    @classmethod
    async def update_user_role_admin(cls, target_user_id: str, new_role: str, admin_user_id: str) -> dict:
        user = await cls.get_user_by_id(target_user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if new_role not in ("USER", "OWNER", "CEO", "ADMIN"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role specified. Must be USER, OWNER, CEO, or ADMIN.")

        if user["userId"] == admin_user_id and new_role not in ("OWNER", "CEO", "ADMIN"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote your own leadership account to regular user")

        async with get_db() as db:
            await db.execute("UPDATE users SET role = ? WHERE userId = ?", (new_role, target_user_id))
            await db.commit()
            await cls.log_activity(db, admin_user_id, "ADMIN_ROLE_UPDATE", f"Changed role of {user['email']} to {new_role}")

        updated = await cls.get_user_by_id(target_user_id)
        return row_to_user_dict(updated)

    @classmethod
    async def get_login_activity_admin(cls, limit: int = 50) -> List[dict]:
        """Fetch recent login audit events with user email, device, and timestamp."""
        async with get_db() as db:
            async with db.execute("""
            SELECT a.id, a.userId, u.email, a.action, a.details, a.ipAddress, a.userAgent, a.createdAt
            FROM audit_logs a
            LEFT JOIN users u ON a.userId = u.userId
            WHERE a.action IN ('LOGIN', 'REGISTER', 'LOGIN_FAILED', 'LOGIN_LOCKED', 'LOGIN_MFA_SUCCESS', 'MFA_FAILED', 'LOGOUT', 'SESSIONS_REVOKED')
            ORDER BY a.id DESC
            LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                results = []
                for r in rows:
                    created = r["createdAt"]
                    date_part = created.split("T")[0] if "T" in created else created[:10]
                    time_part = created.split("T")[1][:8] if "T" in created else created[11:19]
                    ua = r["userAgent"] or "Unknown Device"
                    device = "Browser / Desktop"
                    if "Android" in ua:
                        device = "Android App / Mobile"
                    elif "iPhone" in ua or "iPad" in ua:
                        device = "iOS / Safari"
                    elif "Mobile" in ua:
                        device = "Mobile Browser"
                    elif "Chrome" in ua:
                        device = "Chrome Browser"
                    elif "Firefox" in ua:
                        device = "Firefox Browser"
                    elif "Edge" in ua:
                        device = "Edge Browser"

                    status_val = "FAILED" if ("FAILED" in r["action"] or "LOCKED" in r["action"]) else "SUCCESS"

                    results.append({
                        "id": r["id"],
                        "userId": r["userId"],
                        "email": r["email"] or "Unknown / Deleted",
                        "action": r["action"],
                        "details": r["details"],
                        "ipAddress": r["ipAddress"] or "127.0.0.1",
                        "userAgent": ua,
                        "device": device,
                        "date": date_part,
                        "time": time_part,
                        "createdAt": created,
                        "status": status_val
                    })
                return results

    @classmethod
    async def delete_user_account(cls, user_id: str, confirmation_password: Optional[str] = None) -> bool:
        user = await cls.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")
        
        # If password provided, verify it
        if confirmation_password:
            if not verify_password(confirmation_password, user["passwordHash"]):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password for account deletion")

        # 1. Clean up physical upload files on disk
        user_upload_dir = settings.UPLOAD_DIR / user_id
        if user_upload_dir.exists():
            import shutil
            try:
                shutil.rmtree(user_upload_dir, ignore_errors=True)
            except Exception:
                pass

        # 2. Delete active sessions and user record (Foreign keys ON CASCADE will automatically purge conversations, messages, files, images, voice, projects, preferences, memories, audit logs)
        async with get_db() as db:
            try:
                await db.execute("DELETE FROM active_sessions WHERE userId = ?", (user_id,))
            except Exception:
                pass
            await db.execute("DELETE FROM users WHERE userId = ?", (user_id,))
            await db.commit()

        return True

user_service = UserService()

