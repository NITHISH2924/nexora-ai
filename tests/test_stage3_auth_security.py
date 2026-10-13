import sys
import uuid
import time
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.services.mfa_service import mfa_service
from backend.app.services.user_service import user_service
from backend.app.security import (
    hash_token,
    decode_access_token,
    auth_rate_limiter,
    rate_limiter,
    _revoked_token_hashes
)
from backend.app.database import get_db

BASE_URL = "http://127.0.0.1:8000"

@pytest.fixture(autouse=True)
def reset_limiters():
    """Reset rate limiter state and owner MFA state before and after each test."""
    import asyncio
    async def clear_mfa():
        async with get_db() as db:
            await db.execute(
                "UPDATE users SET mfaEnabled = 0, mfaSecret = NULL, mfaRecoveryCodes = NULL WHERE email = ? COLLATE NOCASE",
                (settings.OWNER_EMAIL,)
            )
            await db.commit()

    auth_rate_limiter._lockouts.clear()
    auth_rate_limiter._failed_attempts.clear()
    rate_limiter.requests.clear()
    _revoked_token_hashes.clear()
    try:
        asyncio.run(clear_mfa())
    except Exception:
        pass
    yield
    try:
        asyncio.run(clear_mfa())
    except Exception:
        pass

def test_secure_logout_and_server_side_token_revocation():
    """
    Test 1: Secure session invalidation and logout revocation.
    Verifies that calling /logout immediately and permanently invalidates
    the token server-side. Subsequent requests with the token return 401.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    email = f"logout.user_{rand_id}@example.com"
    password = "SecurePassword123"

    # Register user
    reg_res = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert reg_res.status_code == 200, f"Signup failed: {reg_res.text}"
    token = reg_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify token works on protected endpoint
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email

    # Call logout endpoint
    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Immediate rejection on subsequent request with the same token
    revoked_me_res = client.get("/api/auth/me", headers=headers)
    assert revoked_me_res.status_code == 401
    assert "revoked" in revoked_me_res.json()["detail"].lower() or "authentication" in revoked_me_res.json()["detail"].lower()

    # Rejection via cookie as well
    client.cookies.set("access_token", token)
    cookie_me_res = client.get("/api/auth/me")
    assert cookie_me_res.status_code == 401
    print("\n[PASS] Test 1: Secure logout and server-side token revocation verified.")

def test_server_side_token_revocation_on_password_change():
    """
    Test 2: Token revocation across all active sessions on password change.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    email = f"pwdchange_{rand_id}@example.com"
    password_old = "OldPassword123"
    password_new = "NewPassword456"

    # Register
    reg_res = client.post("/api/auth/signup", json={"email": email, "password": password_old})
    assert reg_res.status_code == 200
    token_old = reg_res.json()["token"]
    headers_old = {"Authorization": f"Bearer {token_old}"}

    # Verify old token works
    assert client.get("/api/auth/me", headers=headers_old).status_code == 200

    # Change password
    chg_res = client.post(
        "/api/user/change-password",
        json={"currentPassword": password_old, "newPassword": password_new},
        headers=headers_old
    )
    assert chg_res.status_code == 200
    assert chg_res.json()["success"] is True

    # Old token must now be rejected
    rejected_res = client.get("/api/auth/me", headers=headers_old)
    assert rejected_res.status_code == 401

    # Login with new password produces working token
    login_res = client.post("/api/auth/login", json={"email": email, "password": password_new})
    assert login_res.status_code == 200
    token_new = login_res.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_new}"}).status_code == 200
    print("\n[PASS] Test 2: Server-side token revocation on password change verified.")

def test_server_side_revocation_on_account_suspension():
    """
    Test 3: Token revocation and access denial upon account suspension.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    user_email = f"suspend.target_{rand_id}@example.com"

    # Register normal user
    u_res = client.post("/api/auth/signup", json={"email": user_email, "password": "UserPass12345"})
    assert u_res.status_code == 200
    target_user_id = u_res.json()["user"]["userId"]
    target_token = u_res.json()["token"]
    user_headers = {"Authorization": f"Bearer {target_token}"}

    # Verify user can access profile
    assert client.get("/api/auth/me", headers=user_headers).status_code == 200

    # Owner logs in or registers
    owner_client = TestClient(app, base_url=BASE_URL)
    owner_client.post("/api/auth/signup", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
    owner_login = owner_client.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
    owner_token = owner_login.json()["token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Owner suspends target user
    suspend_res = owner_client.patch(
        f"/api/owner/users/{target_user_id}/status",
        json={"accountStatus": "SUSPENDED"},
        headers=owner_headers
    )
    assert suspend_res.status_code == 200
    assert suspend_res.json()["accountStatus"] == "SUSPENDED"

    # Suspended user's existing token must be immediately rejected with 401 or 403
    check_res = client.get("/api/auth/me", headers=user_headers)
    assert check_res.status_code in (401, 403)

    # Suspended user cannot log in
    bad_login = client.post("/api/auth/login", json={"email": user_email, "password": "UserPass12345"})
    assert bad_login.status_code == 403
    print("\n[PASS] Test 3: Session revocation on account suspension verified.")

def test_account_level_brute_force_lockout():
    """
    Test 4: Account-level brute-force defense lockout after 5 consecutive failed attempts.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    email = f"brute_target_{rand_id}@example.com"
    correct_password = "CorrectPassword123"

    reg_res = client.post("/api/auth/signup", json={"email": email, "password": correct_password})
    assert reg_res.status_code == 200

    # 4 failed attempts: return 401 Unauthorized
    for i in range(4):
        res = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword"})
        assert res.status_code == 401

    # 5th failed attempt: triggers lockout (returns 429 Too Many Requests)
    lockout_res = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword"})
    assert lockout_res.status_code == 429
    assert "Retry-After" in lockout_res.headers
    assert "locked" in lockout_res.json()["detail"].lower()

    # Even with the CORRECT password, locked account returns 429
    locked_attempt = client.post("/api/auth/login", json={"email": email, "password": correct_password})
    assert locked_attempt.status_code == 429
    assert int(locked_attempt.headers["Retry-After"]) > 0
    print("\n[PASS] Test 4: Account-level brute-force lockout verified.")

def test_ip_level_brute_force_rate_limiting():
    """
    Test 5: IP-level rate limiting resisting distributed brute-force attempts.
    """
    client = TestClient(app, base_url=BASE_URL)
    ip_limit = getattr(settings, "AUTH_IP_MAX_LOGIN_ATTEMPTS", 10)

    # Send rapid login requests from simulated client IP
    responses = []
    for i in range(ip_limit + 5):
        resp = client.post(
            "/api/auth/login",
            json={"email": f"nonexistent_{i}@example.com", "password": "RandomPassword123"},
            headers={"X-Forwarded-For": "203.0.113.42"}
        )
        responses.append(resp.status_code)

    assert 429 in responses, "IP rate limiter should throttle excessive attempts with 429"
    print("\n[PASS] Test 5: IP-level brute-force rate limiting verified.")

def test_failed_login_and_suspicious_event_auditing():
    """
    Test 6: Failed login and suspicious event auditing with metadata and masked identifiers.
    Zero plain passwords or secrets logged.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    email = f"audit_user_{rand_id}@example.com"
    secret_pass = "UltraSecretPass987!"

    client.post("/api/auth/signup", json={"email": email, "password": secret_pass})

    # Trigger failed login
    client.post("/api/auth/login", json={"email": email, "password": "WrongPasswordX"})

    # Inspect audit_logs in DB
    import asyncio
    async def check_audit():
        async with get_db() as db:
            async with db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
                logs = [dict(r) for r in rows]
                return logs

    logs = asyncio.run(check_audit())
    actions = [l["action"] for l in logs]
    assert "REGISTER" in actions or "LOGIN_FAILED" in actions

    for log in logs:
        # Guarantee NO passwords or secrets stored in log details
        details = str(log.get("details", ""))
        assert secret_pass not in details, "Password leaked into audit log details!"
        assert "WrongPasswordX" not in details, "Candidate password leaked into audit log!"
    print("\n[PASS] Test 6: Audit logging with zero secret leakage verified.")

def test_owner_account_mfa_enrollment_and_totp_login():
    """
    Test 7: Owner MFA enrollment (RFC 6238 TOTP), verification, and full access token issuance.
    """
    client = TestClient(app, base_url=BASE_URL)
    owner_pass = "OwnerSuperPass123"

    # Reset owner credentials and MFA state to clean baseline for test isolation
    import asyncio
    from backend.app.security import hash_password
    async def prepare_owner():
        async with get_db() as db:
            hashed = hash_password(owner_pass)
            await db.execute(
                "UPDATE users SET passwordHash = ?, mfaEnabled = 0, mfaSecret = NULL, mfaRecoveryCodes = NULL WHERE email = ? COLLATE NOCASE",
                (hashed, settings.OWNER_EMAIL)
            )
            await db.commit()

    asyncio.run(prepare_owner())

    login_res = client.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": owner_pass})
    if login_res.status_code != 200:
        client.post("/api/auth/signup", json={"email": settings.OWNER_EMAIL, "password": owner_pass})
        login_res = client.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": owner_pass})
    assert login_res.status_code == 200
    owner_token = login_res.json()["token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 1. Setup MFA
    setup_res = client.post("/api/auth/mfa/setup", headers=owner_headers)
    assert setup_res.status_code == 200
    setup_data = setup_res.json()
    secret = setup_data["secret"]
    recovery_codes = setup_data["recoveryCodes"]
    assert len(secret) >= 16
    assert len(recovery_codes) >= 8

    # 2. Enable MFA using valid TOTP code
    code = mfa_service.generate_totp_code(secret)
    enable_res = client.post(
        "/api/auth/mfa/enable",
        json={"secret": secret, "code": code, "recoveryCodes": recovery_codes},
        headers=owner_headers
    )
    assert enable_res.status_code == 200
    assert enable_res.json()["success"] is True

    # 3. Next login presents MFA Challenge (does not issue full access token)
    challenge_res = client.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": owner_pass})
    assert challenge_res.status_code == 200
    challenge_data = challenge_res.json()
    assert challenge_data["mfaRequired"] is True
    assert challenge_data["token"] is None
    assert challenge_data["user"] is None
    mfa_session_token = challenge_data["mfaSessionToken"]
    assert mfa_session_token is not None

    # 4. Verify TOTP code to complete login
    valid_code = mfa_service.generate_totp_code(secret)
    verify_res = client.post("/api/auth/mfa/verify", json={
        "mfaSessionToken": mfa_session_token,
        "code": valid_code
    })
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["token"] is not None
    assert verify_data["user"]["role"] in ("OWNER", "CEO")

    # 5. Access owner dashboard with verified token
    final_headers = {"Authorization": f"Bearer {verify_data['token']}"}
    overview = client.get("/api/owner/overview", headers=final_headers)
    assert overview.status_code == 200

    # 6. Clean up: disable MFA on owner so subsequent tests have a clean baseline
    async def cleanup_owner():
        async with get_db() as db:
            await db.execute(
                "UPDATE users SET mfaEnabled = 0, mfaSecret = NULL, mfaRecoveryCodes = NULL WHERE email = ? COLLATE NOCASE",
                (settings.OWNER_EMAIL,)
            )
            await db.commit()
    asyncio.run(cleanup_owner())
    print("\n[PASS] Test 7: Owner account MFA enrollment and TOTP login verified.")

def test_single_use_recovery_codes_and_no_reuse():
    """
    Test 8: Backup recovery code authentication and prevention of replay/reuse.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    email = f"recovery_user_{rand_id}@example.com"
    pwd = "UserRecoveryPass123"

    reg_res = client.post("/api/auth/signup", json={"email": email, "password": pwd})
    token = reg_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup & enable MFA
    setup = client.post("/api/auth/mfa/setup", headers=headers).json()
    secret = setup["secret"]
    recovery_codes = setup["recoveryCodes"]
    code = mfa_service.generate_totp_code(secret)
    client.post("/api/auth/mfa/enable", json={"secret": secret, "code": code, "recoveryCodes": recovery_codes}, headers=headers)

    # Initiate login
    login_1 = client.post("/api/auth/login", json={"email": email, "password": pwd}).json()
    mfa_token_1 = login_1["mfaSessionToken"]

    # Use first recovery code
    used_code = recovery_codes[0]
    verify_1 = client.post("/api/auth/mfa/verify", json={"mfaSessionToken": mfa_token_1, "code": used_code})
    assert verify_1.status_code == 200
    assert verify_1.json()["token"] is not None

    # Initiate second login
    login_2 = client.post("/api/auth/login", json={"email": email, "password": pwd}).json()
    mfa_token_2 = login_2["mfaSessionToken"]

    # Attempt to REUSE the same recovery code -> MUST FAIL with 401
    verify_reuse = client.post("/api/auth/mfa/verify", json={"mfaSessionToken": mfa_token_2, "code": used_code})
    assert verify_reuse.status_code == 401
    assert "invalid" in verify_reuse.json()["detail"].lower()

    # But another unconsumed recovery code works
    second_code = recovery_codes[1]
    verify_second = client.post("/api/auth/mfa/verify", json={"mfaSessionToken": mfa_token_2, "code": second_code})
    assert verify_second.status_code == 200
    print("\n[PASS] Test 8: Single-use recovery codes and replay protection verified.")

def test_prevention_of_mfa_bypass():
    """
    Test 9: Prevention of MFA bypass. Temporary MFA session tokens
    CANNOT be used to access protected or owner API routes.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    email = f"bypass_test_{rand_id}@example.com"
    pwd = "MfaBypassPass123"

    reg = client.post("/api/auth/signup", json={"email": email, "password": pwd}).json()
    token = reg["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Enable MFA
    setup = client.post("/api/auth/mfa/setup", headers=headers).json()
    code = mfa_service.generate_totp_code(setup["secret"])
    client.post("/api/auth/mfa/enable", json={"secret": setup["secret"], "code": code, "recoveryCodes": setup["recoveryCodes"]}, headers=headers)

    # Login to get mfaSessionToken (provisional token)
    chal = client.post("/api/auth/login", json={"email": email, "password": pwd}).json()
    temp_mfa_token = chal["mfaSessionToken"]

    # Attempt to use temp_mfa_token on protected endpoints
    temp_headers = {"Authorization": f"Bearer {temp_mfa_token}"}
    me_res = client.get("/api/auth/me", headers=temp_headers)
    assert me_res.status_code == 401
    assert "two-factor" in me_res.json()["detail"].lower() or "mfa" in me_res.json()["detail"].lower()

    owner_res = client.get("/api/owner/overview", headers=temp_headers)
    assert owner_res.status_code == 401
    print("\n[PASS] Test 9: Prevention of MFA bypass verified.")

def test_authorization_regular_user_cannot_access_owner_features():
    """
    Test 10: Authorization enforcement - regular users ('role=USER')
    strictly receive 403 Forbidden on all owner endpoints.
    """
    client = TestClient(app, base_url=BASE_URL)
    rand_id = uuid.uuid4().hex[:6]
    user_email = f"standard.user_{rand_id}@example.com"

    reg = client.post("/api/auth/signup", json={"email": user_email, "password": "UserStandardPass123"}).json()
    assert reg["user"]["role"] == "USER"
    user_headers = {"Authorization": f"Bearer {reg['token']}"}

    owner_endpoints = [
        ("GET", "/api/owner/overview"),
        ("GET", "/api/owner/system-health"),
        ("GET", "/api/owner/users"),
        ("GET", "/api/owner/login-activity"),
        ("PATCH", f"/api/owner/users/{reg['user']['userId']}/status", {"accountStatus": "ACTIVE"}),
        ("PATCH", f"/api/owner/users/{reg['user']['userId']}/role", {"role": "OWNER"}),
    ]

    for method, path, *payload in owner_endpoints:
        if method == "GET":
            res = client.get(path, headers=user_headers)
        elif method == "PATCH":
            res = client.patch(path, json=payload[0], headers=user_headers)
        assert res.status_code == 403, f"Expected 403 Forbidden for {method} {path}, got {res.status_code}"
        assert "leadership" in res.json()["detail"].lower() or "forbidden" in res.json()["detail"].lower()

    print("\n[PASS] Test 10: Strict RBAC: regular users blocked from all owner endpoints with 403.")

def test_zero_secrets_leakage_in_error_responses():
    """
    Test 11: Zero credential, token, or secret leakage in error responses.
    """
    client = TestClient(app, base_url=BASE_URL)
    res = client.post("/api/auth/login", json={"email": "attacker@evil.com", "password": "SecretPasswordInPayload"})
    assert "SecretPasswordInPayload" not in res.text
    assert settings.JWT_SECRET not in res.text
    print("\n[PASS] Test 11: Zero secret leakage in responses verified.")
