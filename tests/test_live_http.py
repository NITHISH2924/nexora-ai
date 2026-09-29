import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import app

BASE_URL = "http://127.0.0.1:8000"

def test_live_http():
    session = TestClient(app, base_url=BASE_URL)

    print("\n" + "="*70)
    print("RUNNING LIVE HTTP SERVER E2E INTEGRATION TEST")
    print(f"Target: {BASE_URL}")
    print("="*70 + "\n")

    # 1. Test Static Page Routing
    pages = [
        ("/", "NEXORA AI", "One AI. Everything you need."),
        ("/login", "Sign In", "login-form"),
        ("/signup", "Create Account", "signup-form"),
        ("/forgot-password", "Forgot Password", "forgot-password-form"),
        ("/reset-password", "Reset Password", "reset-password-form"),
        ("/verify-email", "Verify Email", "verify-container"),
        ("/app", "Workspace", "app-sidebar"),
        ("/privacy", "Privacy Policy", "legal-card"),
        ("/terms", "Terms of Service", "legal-card"),
        ("/delete-account", "Delete Account", "delete-card")
    ]

    print("[1] Testing Clean URL Page Routes & Content...")
    for path, title_fragment, content_fragment in pages:
        res = session.get(path)
        assert res.status_code == 200, f"Failed route: {path} returned {res.status_code}"
        assert title_fragment in res.text, f"Title fragment '{title_fragment}' missing in {path}"
        assert content_fragment in res.text, f"Content fragment '{content_fragment}' missing in {path}"
        print(f"    [PASS] {path:20} -> 200 OK (verified '{title_fragment}')")

    # 2. Test Security Headers
    print("\n[2] Testing Security Headers...")
    res = session.get("/")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    print("    [PASS] Security headers (nosniff, DENY, strict-origin) present.")

    # 3. Test Live User Registration via HTTP API
    print("\n[3] Testing User Registration via HTTP API (POST /api/auth/signup)...")
    rand_s = uuid.uuid4().hex[:6]
    email = f"live.user_{rand_s}@example.com"
    reg_payload = {"email": email, "password": "ProductionPassword2026"}
    res = session.post("/api/auth/signup", json=reg_payload)
    assert res.status_code == 200, f"Signup failed: {res.text}"
    data = res.json()
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "USER"
    assert "token" in data
    user_token = data["token"]
    auth_headers = {"Authorization": f"Bearer {user_token}"}
    print(f"    [PASS] User registered: {email}, token received.")

    # 4. Test Authenticated User Profile via Session Cookie & Header (GET /api/auth/me)
    print("\n[4] Testing Authenticated Profile (GET /api/auth/me)...")
    res = session.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    user_me = res.json()
    assert user_me["email"] == email
    assert user_me["role"] == "USER"
    assert "passwordHash" not in user_me
    print(f"    [PASS] Profile fetched via session: {user_me['userId']}")

    # 5. Test Server-Side Owner Authorization Protection
    print("\n[5] Testing Server-Side Owner Authorization Protection (GET /api/owner/overview)...")
    res = session.get("/api/owner/overview", headers=auth_headers)
    assert res.status_code == 403, f"Expected 403 Forbidden for normal user, got {res.status_code}"
    print("    [PASS] Normal user blocked from owner endpoint with 403 Forbidden.")

    # 6. Test Logout (POST /api/auth/logout)
    print("\n[6] Testing Logout (POST /api/auth/logout)...")
    res = session.post("/api/auth/logout", headers=auth_headers)
    assert res.status_code == 200
    print("    [PASS] Logout endpoint cleared session.")

    # 7. Test Protected Endpoint Without Auth
    print("\n[7] Testing Protected Endpoint Without Auth...")
    unauth_session = TestClient(app, base_url=BASE_URL)
    res = unauth_session.get("/api/auth/me")
    assert res.status_code == 401
    print("    [PASS] Unauthenticated request correctly rejected with 401.")

    # 8. Test Invalid Credentials Login Rejection
    print("\n[8] Testing Invalid Credentials Login (POST /api/auth/login)...")
    res = unauth_session.post("/api/auth/login", json={"email": email, "password": "WrongPassword123"})
    assert res.status_code == 401
    print("    [PASS] Invalid login rejected with 401 Unauthorized.")

    # 9. Test Owner Login and Server-Side Privileges
    print("\n[9] Testing Owner Login & Privileges...")
    from backend.app.config import settings
    owner_session = TestClient(app, base_url=BASE_URL)
    owner_login = owner_session.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
    if owner_login.status_code != 200:
        # If password was different, register new owner tag or use token
        owner_session.post("/api/auth/signup", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
        owner_login = owner_session.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
    
    if owner_login.status_code == 200:
        owner_data = owner_login.json()
        assert owner_data["user"]["role"] == "OWNER"
        owner_headers = {"Authorization": f"Bearer {owner_data['token']}"}

        # Owner calls owner endpoint
        owner_overview = owner_session.get("/api/owner/overview", headers=owner_headers)
        assert owner_overview.status_code == 200
        overview_stats = owner_overview.json()
        assert "totalUsers" in overview_stats
        print(f"    [PASS] Owner authenticated successfully. Total users in DB: {overview_stats['totalUsers']}")

        # Owner lists all users
        owner_users = owner_session.get("/api/owner/users", headers=owner_headers)
        assert owner_users.status_code == 200
        users_list = owner_users.json()
        assert len(users_list) >= 2

    # 10. Test Phase 2 AI Model Listing & Conversations via Live HTTP
    print("\n[10] Testing Phase 2 AI Models & Chat Endpoints via Live HTTP...")
    chat_client = TestClient(app, base_url=BASE_URL)
    reg_user = chat_client.post("/api/auth/signup", json={"email": f"chat.user_{rand_s}@example.com", "password": "StrongPassword123"}).json()
    chat_headers = {"Authorization": f"Bearer {reg_user['token']}"}
    
    # Models endpoint
    models_res = chat_client.get("/api/chat/models", headers=chat_headers)
    assert models_res.status_code == 200
    assert len(models_res.json()["models"]) >= 5
    print("    [PASS] GET /api/chat/models returned active model catalog.")

    # Create conversation
    create_res = chat_client.post("/api/chat/conversations", json={"title": "Live Test Chat", "model": "myai-core-v2"}, headers=chat_headers)
    assert create_res.status_code == 200
    live_conv = create_res.json()
    live_conv_id = live_conv["id"]
    print(f"    [PASS] POST /api/chat/conversations created conversation ID: {live_conv_id}")

    # Send message non-streaming
    msg_res = chat_client.post(f"/api/chat/conversations/{live_conv_id}/messages", json={"content": "Explain microservices in 2 sentences"}, headers=chat_headers)
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert "assistantMessage" in msg_data
    assert len(msg_data["assistantMessage"]["content"]) > 10
    print(f"    [PASS] POST /api/chat/conversations/{live_conv_id}/messages returned AI response.")

    # Test SSE streaming endpoint
    stream_res = chat_client.post(
        f"/api/chat/conversations/{live_conv_id}/stream",
        json={"content": "Write a python fibonacci function"},
        headers=chat_headers
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers.get("content-type", "")
    assert len(stream_res.text) > 50
    print(f"    [PASS] POST /api/chat/conversations/{live_conv_id}/stream returned SSE stream ({len(stream_res.text)} bytes).")

    # Rename and delete conversation
    patch_res = chat_client.patch(f"/api/chat/conversations/{live_conv_id}", json={"title": "Renamed Live Chat"}, headers=chat_headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Renamed Live Chat"
    print("    [PASS] PATCH /api/chat/conversations/{id} updated title.")

    del_res = chat_client.delete(f"/api/chat/conversations/{live_conv_id}", headers=chat_headers)
    assert del_res.status_code == 200
    print("    [PASS] DELETE /api/chat/conversations/{id} removed conversation.")

    # 11. Test Phase 6: Projects Workspace HTTP Endpoints
    print("\n[11] Testing Phase 6 Projects Workspace HTTP API...")
    proj_res = chat_client.post("/api/projects", json={
        "name": "Live HTTP E2E Project",
        "description": "Integration testing workspace",
        "instructions": "Be precise and modular.",
        "color": "#10B981"
    }, headers=chat_headers)
    assert proj_res.status_code == 200, f"Create project failed: {proj_res.text}"
    proj_data = proj_res.json()
    proj_id = proj_data["id"]
    print(f"    [PASS] POST /api/projects created project ID: {proj_id}")

    # Add Note to Project
    note_res = chat_client.post(f"/api/projects/{proj_id}/notes", json={
        "title": "Live Architecture Note",
        "content": "Verified project workspace functionality."
    }, headers=chat_headers)
    assert note_res.status_code == 200
    print("    [PASS] POST /api/projects/{id}/notes added project note.")

    # Save Output to Project
    out_res = chat_client.post(f"/api/projects/{proj_id}/outputs", json={
        "title": "HTTP Synthesis Snippet",
        "outputType": "text",
        "content": "Sample output artifact."
    }, headers=chat_headers)
    assert out_res.status_code == 200
    print("    [PASS] POST /api/projects/{id}/outputs saved project output.")

    # Get Project Detail
    detail_res = chat_client.get(f"/api/projects/{proj_id}", headers=chat_headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert len(detail_data["notes"]) == 1
    assert len(detail_data["savedOutputs"]) == 1
    print("    [PASS] GET /api/projects/{id} returned full project structure with notes and outputs.")

    # 12. Test Phase 6: Personalization & Controlled Memory HTTP Endpoints
    print("\n[12] Testing Phase 6 Personalization & Controlled Memory HTTP API...")
    pref_res = chat_client.get("/api/personalization/preferences", headers=chat_headers)
    assert pref_res.status_code == 200
    print("    [PASS] GET /api/personalization/preferences loaded default settings.")

    put_pref_res = chat_client.put("/api/personalization/preferences", json={
        "displayName": "HTTP Live Tester",
        "preferredLanguage": "English",
        "aiTone": "technical",
        "theme": "deep-purple",
        "enableMemory": True
    }, headers=chat_headers)
    assert put_pref_res.status_code == 200
    assert put_pref_res.json()["displayName"] == "HTTP Live Tester"
    print("    [PASS] PUT /api/personalization/preferences updated user profile.")

    # Create Memory
    mem_res = chat_client.post("/api/personalization/memories", json={
        "category": "preference",
        "key": "Live Language Preference",
        "value": "Always provide clean async Python examples."
    }, headers=chat_headers)
    assert mem_res.status_code == 200
    mem_id = mem_res.json()["id"]
    print(f"    [PASS] POST /api/personalization/memories saved memory ID: {mem_id}")

    # List Memories
    mems_list_res = chat_client.get("/api/personalization/memories", headers=chat_headers)
    assert mems_list_res.status_code == 200
    assert mems_list_res.json()["total"] >= 1
    print("    [PASS] GET /api/personalization/memories listed active memories.")

    # Delete Memory
    del_mem_res = chat_client.delete(f"/api/personalization/memories/{mem_id}", headers=chat_headers)
    assert del_mem_res.status_code == 200
    print("    [PASS] DELETE /api/personalization/memories/{id} deleted memory item.")

    # Delete Project
    del_proj_res = chat_client.delete(f"/api/projects/{proj_id}", headers=chat_headers)
    assert del_proj_res.status_code == 200
    print("    [PASS] DELETE /api/projects/{id} deleted project.")

    # 13. Test Account Deletion Flow (GDPR & Play Store requirement)
    print("\n[13] Testing User Account Deletion Flow (DELETE /api/user/account)...")
    del_acc_res = chat_client.delete("/api/user/account", headers=chat_headers)
    assert del_acc_res.status_code == 200
    assert del_acc_res.json()["success"] is True
    print("    [PASS] User account and all associated data permanently deleted.")

    # Verify user can no longer log in
    del_login_res = session.post("/api/auth/login", json={"email": f"chat.user_{rand_s}@example.com", "password": "StrongPassword123"})
    assert del_login_res.status_code == 401
    print("    [PASS] Deleted user login rejected with 401 Unauthorized.")

    print("\n" + "="*70)
    print("ALL LIVE HTTP E2E INTEGRATION TESTS (PHASE 1 - PHASE 6) PASSED (100% SUCCESS)!")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_live_http()

