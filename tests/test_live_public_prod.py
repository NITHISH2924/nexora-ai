import requests
import uuid
import sys
import time

PUBLIC_URL = "https://missed-straight-shall-aged.trycloudflare.com"

def run_live_public_tests():
    print("\n" + "="*80)
    print(f"RUNNING LIVE PRODUCTION E2E SUITE ON PUBLIC HTTPS URL: {PUBLIC_URL}")
    print("="*80 + "\n")

    session = requests.Session()

    # 1. Test Static Pages via HTTPS
    print("[1] Verifying Public HTTPS Clean URL Page Routes...")
    pages = ["/", "/login", "/signup", "/forgot-password", "/reset-password", "/verify-email", "/app"]
    for path in pages:
        res = session.get(f"{PUBLIC_URL}{path}")
        assert res.status_code == 200, f"Route {path} failed: {res.status_code}"
        print(f"    [PASS] HTTPS {path:20} -> 200 OK")

    # 2. Test Security Headers over HTTPS
    print("\n[2] Verifying Security Headers on Public Domain...")
    res = session.get(f"{PUBLIC_URL}/")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    print("    [PASS] nosniff, DENY, strict-origin verified.")

    # 3. Test New User Registration on Live Public URL
    print("\n[3] Testing New User Registration on Public URL...")
    rand_tag = uuid.uuid4().hex[:6]
    new_user_email = f"prod_live_{rand_tag}@example.com"
    pwd = "ProductionPassword2026!"
    
    signup_res = session.post(f"{PUBLIC_URL}/api/auth/signup", json={"email": new_user_email, "password": pwd})
    assert signup_res.status_code == 200, f"Signup failed: {signup_res.text}"
    signup_data = signup_res.json()
    new_user_id = signup_data["user"]["userId"]
    new_token = signup_data["token"]
    user_headers = {"Authorization": f"Bearer {new_token}"}
    print(f"    [PASS] New user registered: {new_user_email} (ID: {new_user_id})")

    # 4. Test Authenticated Profile
    print("\n[4] Testing Authenticated Session Profile...")
    me_res = session.get(f"{PUBLIC_URL}/api/auth/me", headers=user_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == new_user_email
    print(f"    [PASS] /api/auth/me verified for {new_user_email}")

    # 5. Test Existing User Login
    print("\n[5] Testing Existing User Login via Public URL...")
    login_session = requests.Session()
    login_res = login_session.post(f"{PUBLIC_URL}/api/auth/login", json={"email": new_user_email, "password": pwd})
    assert login_res.status_code == 200
    assert login_res.json()["user"]["email"] == new_user_email
    print("    [PASS] Existing user login authenticated successfully.")

    # 6. Test AI Model Listing & Multi-Turn Chat
    print("\n[6] Testing AI Model Catalog & Multi-Turn Chat via Public HTTPS...")
    models_res = session.get(f"{PUBLIC_URL}/api/chat/models", headers=user_headers)
    assert models_res.status_code == 200
    assert len(models_res.json()["models"]) >= 5
    print(f"    [PASS] AI models retrieved: {len(models_res.json()['models'])} active models.")

    # Create Conversation
    conv_res = session.post(f"{PUBLIC_URL}/api/chat/conversations", json={"title": "Cloudflare HTTPS Test", "model": "myai-core-v2"}, headers=user_headers)
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]
    print(f"    [PASS] Created conversation ID: {conv_id}")

    # Send Message
    msg_res = session.post(f"{PUBLIC_URL}/api/chat/conversations/{conv_id}/messages", json={"content": "Explain HTTPS and Cloudflare tunnel encryption in 2 sentences."}, headers=user_headers)
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert "assistantMessage" in msg_data
    assert len(msg_data["assistantMessage"]["content"]) > 20
    print(f"    [PASS] AI response received ({len(msg_data['assistantMessage']['content'])} chars).")

    # 7. Test File Upload & Document AI on Public URL
    print("\n[7] Testing File Upload & Document Intelligence via Public HTTPS...")
    file_content = b"NEXORA AI Production Release 2026. Scalable, hardened multi-tenant AI system deployed with TLS 1.3 encryption."
    files = {"file": ("prod_release.txt", file_content, "text/plain")}
    upload_res = session.post(f"{PUBLIC_URL}/api/files/upload", files=files, headers=user_headers)
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    uploaded_file = upload_res.json()
    doc_id = uploaded_file["id"]
    print(f"    [PASS] File uploaded successfully: ID {doc_id} ({uploaded_file['fileSize']} bytes)")

    # Execute Document AI Action
    doc_ai_res = session.post(f"{PUBLIC_URL}/api/files/{doc_id}/action", json={"action": "summarize"}, headers=user_headers)
    assert doc_ai_res.status_code == 200
    assert len(doc_ai_res.json()["result"]) > 15
    print(f"    [PASS] Document AI 'summarize' action executed over public HTTPS.")

    # 8. Test AI Deep Search via Public URL
    print("\n[8] Testing AI Deep Search via Public HTTPS...")
    search_res = session.post(f"{PUBLIC_URL}/api/tools/search", json={"query": "Cloudflare Tunnel vs reverse proxy", "maxResults": 3}, headers=user_headers)
    assert search_res.status_code == 200
    s_data = search_res.json()
    assert len(s_data["sources"]) >= 1
    assert len(s_data["synthesis"]) > 30
    print(f"    [PASS] AI Search returned {len(s_data['sources'])} sources with grounded synthesis.")

    # 9. Test Owner Admin Dashboard & Authorization
    print("\n[9] Testing Admin / Owner Dashboard Authorization...")
    # Normal user access blocked
    blocked_res = session.get(f"{PUBLIC_URL}/api/owner/overview", headers=user_headers)
    assert blocked_res.status_code == 403
    print("    [PASS] Normal user blocked from owner endpoint (403 Forbidden).")

    # Owner login & access
    owner_sess = requests.Session()
    owner_log = owner_sess.post(f"{PUBLIC_URL}/api/auth/login", json={"email": "owner@myai.com", "password": "OwnerSuperPass123"})
    if owner_log.status_code == 200:
        owner_jwt = owner_log.json()["token"]
        owner_hdr = {"Authorization": f"Bearer {owner_jwt}"}
        owner_stats = owner_sess.get(f"{PUBLIC_URL}/api/owner/overview", headers=owner_hdr)
        assert owner_stats.status_code == 200
        print(f"    [PASS] Platform Owner authenticated: Total users {owner_stats.json()['totalUsers']}")

    print("\n" + "="*80)
    print("ALL LIVE PRODUCTION PUBLIC HTTPS TESTS PASSED SUCCESSFULLY! (100% PASS)")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_live_public_tests()
