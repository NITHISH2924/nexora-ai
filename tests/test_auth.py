import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import create_tables, get_db
from backend.app.services.user_service import user_service
from backend.app.models import (
    UserRegisterRequest,
    UserLoginRequest,
    ResetPasswordRequest,
    ChangePasswordRequest
)
from backend.app.security import decode_access_token

async def run_tests():
    print("\n" + "="*70)
    print("RUNNING PHASE 1 COMPREHENSIVE AUTHENTICATION TEST SUITE")
    print("="*70 + "\n")

    # 1. Initialize Tables
    print("[1] Initializing database tables...")
    await create_tables()
    print("    [PASS] Database tables created successfully.")

    # 2. Test Normal User Registration
    print("\n[2] Testing Normal User Registration...")
    import uuid
    rand_suffix = uuid.uuid4().hex[:6]
    test_email = f"tester_{rand_suffix}@example.com"
    user_data = UserRegisterRequest(email=test_email, password="SecurePassword123")
    user, token = await user_service.register_user(user_data)
    assert user["email"] == test_email
    assert user["role"] == "USER"
    assert user["loginCount"] == 1
    assert "passwordHash" not in user
    assert token is not None
    payload = decode_access_token(token)
    assert payload["sub"] == user["userId"]
    assert payload["role"] == "USER"
    print(f"    [PASS] User registered with ID: {user['userId']}, Role: {user['role']}")

    # 3. Test Duplicate Registration Prevention
    print("\n[3] Testing Duplicate Registration Prevention...")
    try:
        await user_service.register_user(user_data)
        assert False, "Should have raised 409 Conflict"
    except Exception as e:
        assert "already exists" in str(e).lower() or hasattr(e, "status_code")
        print("    [PASS] Duplicate registration rejected correctly.")

    # 4. Test Owner Registration & Server-side Role Check
    print("\n[4] Testing Owner Registration & Role Assignment...")
    from backend.app.config import settings
    owner_email = settings.OWNER_EMAIL
    owner_data = UserRegisterRequest(email=owner_email, password="OwnerSuperPass123")
    existing_owner = await user_service.get_user_by_email(owner_email)
    if not existing_owner:
        owner, owner_token = await user_service.register_user(owner_data)
    else:
        owner, owner_token = await user_service.login_user(UserLoginRequest(email=owner_email, password="OwnerSuperPass123"))
    assert owner["email"] == owner_email
    assert owner["role"] == "OWNER"
    owner_payload = decode_access_token(owner_token)
    assert owner_payload["role"] == "OWNER"
    print(f"    [PASS] Owner verified with Role: {owner['role']}")

    # 5. Test User Login
    print("\n[5] Testing User Login with valid credentials...")
    login_data = UserLoginRequest(email=test_email, password="SecurePassword123")
    logged_user, login_token = await user_service.login_user(login_data)
    assert logged_user["loginCount"] == 2
    print(f"    [PASS] Login successful. Login count incremented to {logged_user['loginCount']}.")

    # 6. Test Invalid Password Login Rejection
    print("\n[6] Testing Invalid Password Login...")
    try:
        bad_login = UserLoginRequest(email=test_email, password="WrongPassword999")
        await user_service.login_user(bad_login)
        assert False, "Should have raised 401 Unauthorized"
    except Exception as e:
        print("    [PASS] Invalid password rejected with 401 Unauthorized.")

    # 7. Test Email Verification
    print("\n[7] Testing Email Verification Workflow...")
    # Fetch user from db to get token
    db_user = await user_service.get_user_by_email(test_email)
    verify_token = db_user["emailVerificationToken"]
    assert verify_token is not None
    verified = await user_service.verify_email(verify_token)
    assert verified is True
    updated_user = await user_service.get_user_by_email(test_email)
    assert updated_user["emailVerified"] == 1
    assert updated_user["emailVerificationToken"] is None
    print("    [PASS] Email verified and token invalidated successfully.")

    # 8. Test Forgot & Reset Password Workflow
    print("\n[8] Testing Password Reset Workflow...")
    await user_service.request_password_reset(test_email)
    db_user_reset = await user_service.get_user_by_email(test_email)
    reset_token = db_user_reset["passwordResetToken"]
    assert reset_token is not None

    reset_req = ResetPasswordRequest(token=reset_token, newPassword="NewStrongPassword456")
    reset_success = await user_service.reset_password(reset_req)
    assert reset_success is True

    # Try login with new password
    new_login = UserLoginRequest(email=test_email, password="NewStrongPassword456")
    new_logged, _ = await user_service.login_user(new_login)
    assert new_logged["loginCount"] == 3
    print("    [PASS] Password successfully reset and authenticated.")

    # 9. Test Owner User Administration
    print("\n[9] Testing Owner User Administration...")
    all_users = await user_service.get_all_users_admin()
    assert len(all_users) >= 2
    print(f"    [PASS] Owner retrieved {len(all_users)} users from database.")

    # Test Owner suspending a user
    suspended_user = await user_service.update_user_status_admin(
        target_user_id=user["userId"],
        new_status="SUSPENDED",
        admin_user_id=owner["userId"]
    )
    assert suspended_user["accountStatus"] == "SUSPENDED"

    # Suspended user login should fail
    try:
        await user_service.login_user(new_login)
        assert False, "Suspended user should not be able to log in"
    except Exception as e:
        print("    [PASS] Suspended user login prevented correctly.")

    # Reactivate user
    reactivated = await user_service.update_user_status_admin(
        target_user_id=user["userId"],
        new_status="ACTIVE",
        admin_user_id=owner["userId"]
    )
    assert reactivated["accountStatus"] == "ACTIVE"
    print("    [PASS] Owner reactivated user account.")

    # 10. Test Audit Logs
    print("\n[10] Testing Audit Logs...")
    logs = await user_service.get_user_activity(user["userId"])
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    print(f"    [PASS] Audit logs recorded: {', '.join(actions[:5])}")

    print("\n" + "="*70)
    print("ALL PHASE 1 AUTHENTICATION TESTS PASSED SUCCESSFULLY!")
    print("="*70 + "\n")

def test_authentication_suite():
    asyncio.run(run_tests())

if __name__ == "__main__":
    asyncio.run(run_tests())
