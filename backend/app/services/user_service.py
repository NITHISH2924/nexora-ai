import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import aiosqlite
from fastapi import HTTPException, status
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.security import (
    hash_password,
    verify_password,
    generate_secure_token,
    create_access_token
)
from backend.app.models import (
    UserRegisterRequest,
    UserResponse,
    UserLoginRequest,
    ResetPasswordRequest,
    ChangePasswordRequest
)
from backend.app.services.email_service import email_service

def row_to_user_dict(row: aiosqlite.Row) -> dict:
    """Convert sqlite Row to safe user dict for UserResponse."""
    return {
        "userId": row["userId"],
        "email": row["email"],
        "role": row["role"],
        "accountCreatedAt": row["accountCreatedAt"],
        "lastLoginAt": row["lastLoginAt"],
        "loginCount": row["loginCount"],
        "accountStatus": row["accountStatus"],
        "emailVerified": bool(row["emailVerified"])
    }

class UserService:
    @staticmethod
    async def log_activity(db: aiosqlite.Connection, user_id: str, action: str, details: Optional[str] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO audit_logs (userId, action, details, ipAddress, userAgent, createdAt) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, details, ip_address, user_agent, now)
        )
        await db.commit()

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
            async with db.execute("SELECT * FROM users WHERE userId = ?", (user_id,)) as cursor:
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
        
        # Email verification token valid for 24 hours
        verify_token = generate_secure_token()
        verify_expires = (now_dt + timedelta(hours=24)).isoformat()
        
        # Default accountStatus is ACTIVE so users can sign in immediately while verification email is sent
        account_status = "ACTIVE"
        email_verified = 1 if role in ("OWNER", "CEO") else 0

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
            await db.commit()
            await cls.log_activity(db, user_id, "REGISTER", f"Account created with role {role}", ip_address, user_agent)

        # Dispatch verification email
        if not email_verified:
            email_service.send_verification_email(clean_email, verify_token)

        # Generate JWT session token
        token_payload = {
            "sub": user_id,
            "email": clean_email,
            "role": role
        }
        token = create_access_token(token_payload)
        
        user_profile = {
            "userId": user_id,
            "email": clean_email,
            "role": role,
            "accountCreatedAt": created_at,
            "lastLoginAt": created_at,
            "loginCount": 1,
            "accountStatus": account_status,
            "emailVerified": bool(email_verified)
        }
        return user_profile, token

    @classmethod
    async def login_user(cls, data: UserLoginRequest, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> tuple[dict, str]:
        clean_email = data.email.strip().lower()
        user = await cls.get_user_by_email(clean_email)
        
        if not user or not verify_password(data.password, user["passwordHash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if user["accountStatus"] == "SUSPENDED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been suspended. Please contact support."
            )

        now = datetime.now(timezone.utc).isoformat()
        new_count = user["loginCount"] + 1

        async with get_db() as db:
            await db.execute(
                "UPDATE users SET lastLoginAt = ?, loginCount = ? WHERE userId = ?",
                (now, new_count, user["userId"])
            )
            await db.commit()
            await cls.log_activity(db, user["userId"], "LOGIN", "Successful login", ip_address, user_agent)

        # Calculate expiration
        expire_delta = timedelta(days=30) if data.rememberMe else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        token_payload = {
            "sub": user["userId"],
            "email": user["email"],
            "role": user["role"]
        }
        token = create_access_token(token_payload, expires_delta=expire_delta)

        user_profile = {
            "userId": user["userId"],
            "email": user["email"],
            "role": user["role"],
            "accountCreatedAt": user["accountCreatedAt"],
            "lastLoginAt": now,
            "loginCount": new_count,
            "accountStatus": user["accountStatus"],
            "emailVerified": bool(user["emailVerified"])
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
        query = "SELECT userId, email, role, accountCreatedAt, lastLoginAt, loginCount, accountStatus, emailVerified FROM users WHERE 1=1"
        params = []
        if search and search.strip():
            query += " AND email LIKE ?"
            params.append(f"%{search.strip()}%")
        if role_filter and role_filter.strip():
            query += " AND role = ?"
            params.append(role_filter.strip().upper())
        if status_filter and status_filter.strip():
            query += " AND accountStatus = ?"
            params.append(status_filter.strip().upper())
        query += " ORDER BY accountCreatedAt DESC"

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
            WHERE a.action IN ('LOGIN', 'REGISTER')
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
                        "status": "SUCCESS"
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

        # 2. Delete user record (Foreign keys ON CASCADE will automatically purge conversations, messages, files, images, voice, projects, preferences, memories, audit logs)
        async with get_db() as db:
            await db.execute("DELETE FROM users WHERE userId = ?", (user_id,))
            await db.commit()

        return True

user_service = UserService()

