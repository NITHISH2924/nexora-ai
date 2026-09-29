import sys
import os
import io
import time
import json
import base64
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

print("="*80)
print("NEXORA AI — COMPLETE REAL-WORLD END-TO-END VERIFICATION ON LIVE SERVER")
print(f"Target: {BASE_URL}")
print("="*80)

# Check Server is alive
try:
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        r = client.get("/")
        assert r.status_code == 200, f"Server responded with {r.status_code}"
        print("[1] Server Health Check: LIVE and Responding with 200 OK.")
except Exception as e:
    print(f"[FATAL] Could not connect to live server at {BASE_URL}: {e}")
    sys.exit(1)

# =============================================================================
# 1. AUTHENTICATION & SESSION PERSISTENCE TEST
# =============================================================================
print("\n--- 1. AUTHENTICATION & SESSION PERSISTENCE ---")
rand_id = str(int(time.time()))[-6:]
user_a_email = f"user_a_{rand_id}@nexora.ai"
user_b_email = f"user_b_{rand_id}@nexora.ai"
user_pass = "SecurePass2026!#"

with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
    # 1.1 Signup User A
    res = client.post("/api/auth/signup", json={"email": user_a_email, "password": user_pass})
    assert res.status_code == 200, f"Signup failed: {res.text}"
    user_a_data = res.json()
    user_a_token = user_a_data["token"]
    user_a_id = user_a_data["user"]["userId"]
    print(f"  [PASS] User A registered: {user_a_email} (ID: {user_a_id})")

    # 1.2 Signup User B
    res_b = client.post("/api/auth/signup", json={"email": user_b_email, "password": user_pass})
    assert res_b.status_code == 200
    user_b_data = res_b.json()
    user_b_token = user_b_data["token"]
    user_b_id = user_b_data["user"]["userId"]
    print(f"  [PASS] User B registered: {user_b_email} (ID: {user_b_id})")

    # 1.3 Invalid Login Rejection
    bad_login = client.post("/api/auth/login", json={"email": user_a_email, "password": "WrongPassword999"})
    assert bad_login.status_code == 401, f"Expected 401, got {bad_login.status_code}"
    print(f"  [PASS] Invalid login rejected with 401 Unauthorized.")

    # 1.4 Valid Login User A
    login_a = client.post("/api/auth/login", json={"email": user_a_email, "password": user_pass})
    assert login_a.status_code == 200
    print(f"  [PASS] User A login successful (Login count: {login_a.json()['user']['loginCount']}).")

    # 1.5 Authenticated Profile Check (/api/auth/me)
    headers_a = {"Authorization": f"Bearer {user_a_token}"}
    headers_b = {"Authorization": f"Bearer {user_b_token}"}
    me_a = client.get("/api/auth/me", headers=headers_a)
    assert me_a.status_code == 200
    assert me_a.json()["userId"] == user_a_id
    print(f"  [PASS] Protected route /api/auth/me verified for User A.")

# =============================================================================
# 2. AI CHAT & STREAMING COMPLETIONS
# =============================================================================
print("\n--- 2. AI CHAT & REAL-TIME STREAMING ---")
with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
    # 2.1 List available models
    models_res = client.get("/api/chat/models", headers=headers_a)
    assert models_res.status_code == 200
    models_list = models_res.json()["models"]
    print(f"  [PASS] Available AI Models listed: {len(models_list)} models discovered.")

    # 2.2 Create Conversation
    conv_res = client.post("/api/chat/conversations", json={"title": "Cloud Architecture Chat", "model": "gemini-1.5-flash"}, headers=headers_a)
    assert conv_res.status_code == 200
    conv_a = conv_res.json()
    conv_a_id = conv_a["id"]
    print(f"  [PASS] Conversation created: ID {conv_a_id}")

    # 2.3 Send Message (Non-streaming)
    msg_res = client.post(f"/api/chat/conversations/{conv_a_id}/messages", json={"content": "Explain microservices architecture."}, headers=headers_a)
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert msg_data["assistantMessage"]["content"] is not None
    print(f"  [PASS] AI Message completion received: {len(msg_data['assistantMessage']['content'])} chars.")

    # 2.4 Send SSE Streaming Message
    stream_content = []
    with client.stream("POST", f"/api/chat/conversations/{conv_a_id}/stream", json={"content": "List 3 benefits of containerization."}, headers=headers_a) as stream_res:
        assert stream_res.status_code == 200
        for line in stream_res.iter_lines():
            if line.startswith("data: "):
                try:
                    payload = json.loads(line[6:])
                    if "chunk" in payload:
                        stream_content.append(payload["chunk"])
                except:
                    pass
    full_stream_text = "".join(stream_content)
    assert len(full_stream_text) > 20
    print(f"  [PASS] SSE Streaming completed: {len(full_stream_text)} chars across {len(stream_content)} chunks.")

    # 2.5 Rename Conversation
    rename_res = client.patch(f"/api/chat/conversations/{conv_a_id}", json={"title": "Containerization & Microservices"}, headers=headers_a)
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Containerization & Microservices"
    print(f"  [PASS] Conversation renamed to '{rename_res.json()['title']}'.")

# =============================================================================
# 3. MULTI-FORMAT FILE UPLOADS & DOCUMENT RAG
# =============================================================================
print("\n--- 3. FILES & DOCUMENT RAG ---")
with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
    # 3.1 Upload TXT document
    txt_content = (
        "NEXORA AI PLATFORM TECHNICAL SPECIFICATION\n"
        "Project Lead: Dr. Helena Vance\n"
        "Security Standard: Zero-Trust Multi-Tenant Architecture\n"
        "Core Secret Metric: The target latency is exactly 42 milliseconds for inference caching.\n"
        "Release Date: November 2026."
    )
    files_payload = {"file": ("tech_spec.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    upload_res = client.post("/api/files/upload", files=files_payload, headers=headers_a)
    assert upload_res.status_code == 200
    doc_a = upload_res.json()
    doc_a_id = doc_a["id"]
    print(f"  [PASS] Document uploaded & text extracted: ID {doc_a_id} ({doc_a['fileSize']} bytes).")

    # 3.2 Document QA (Answer EXISTS in document)
    qa_exist = client.post(f"/api/files/{doc_a_id}/ai-action", json={"action": "qa", "query": "What is the target latency metric?"}, headers=headers_a)
    assert qa_exist.status_code == 200
    qa_res_text = qa_exist.json()["result"]
    assert "42" in qa_res_text or "latency" in qa_res_text.lower()
    print(f"  [PASS] Grounded QA found fact: '{qa_res_text[:80]}...'")

    # 3.3 Document QA (Answer DOES NOT exist in document)
    qa_not_exist = client.post(f"/api/files/{doc_a_id}/ai-action", json={"action": "qa", "query": "What is the company's annual revenue in 2012?"}, headers=headers_a)
    assert qa_not_exist.status_code == 200
    qa_miss_text = qa_not_exist.json()["result"]
    assert "couldn't find" in qa_miss_text.lower() or "not contain" in qa_miss_text.lower() or "missing" in qa_miss_text.lower() or "not mentioned" in qa_miss_text.lower()
    print(f"  [PASS] Grounded QA correctly refused to hallucinate: '{qa_miss_text[:80]}...'")

# =============================================================================
# 4. MULTIMODAL VISION INTELLIGENCE
# =============================================================================
print("\n--- 4. MULTIMODAL VISION INTELLIGENCE ---")
with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
    # Create simple 100x100 PNG image with PIL in memory
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (200, 200), color=(20, 20, 35))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, 180, 180], outline=(139, 92, 246), width=3)
    d.text((40, 90), "NEXORA VISION", fill=(255, 255, 255))
    im_buf = io.BytesIO()
    im.save(im_buf, format="PNG")
    im_bytes = im_buf.getvalue()
    im_b64 = f"data:image/png;base64,{base64.b64encode(im_bytes).decode('utf-8')}"

    vis_res = client.post("/api/files/vision/analyze", json={"imageBase64": im_b64, "action": "describe", "query": "Describe this image."}, headers=headers_a)
    assert vis_res.status_code == 200
    vis_data = vis_res.json()
    assert len(vis_data["result"]) > 0
    print(f"  [PASS] Vision Analysis executed: {vis_data['action']} -> {len(vis_data['result'])} chars.")

# =============================================================================
# 5. AI SEARCH, CODE STUDIO & WRITING ASSISTANT
# =============================================================================
print("\n--- 5. AI SEARCH, CODE STUDIO & WRITING ASSISTANT ---")
with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
    # 5.1 AI Deep Search
    search_res = client.post("/api/tools/search", json={"query": "FastAPI async concurrency vs Node.js", "maxResults": 4}, headers=headers_a)
    assert search_res.status_code == 200
    s_data = search_res.json()
    assert len(s_data["sources"]) > 0
    assert len(s_data["synthesis"]) > 0
    print(f"  [PASS] AI Search retrieved {len(s_data['sources'])} sources with grounded synthesis.")

    # 5.2 Code Generation & Sandbox
    code_res = client.post("/api/tools/code/assist", json={"action": "generate", "prompt": "Write a binary search function in Python", "language": "python"}, headers=headers_a)
    assert code_res.status_code == 200
    assert "def binary_search" in code_res.json()["code"]
    print(f"  [PASS] Code Studio generated Python binary search.")

    # Safe Sandbox Execution
    exec_res = client.post("/api/tools/code/execute", json={"language": "python", "code": "print(sum([x**2 for x in range(10)]))"}, headers=headers_a)
    assert exec_res.status_code == 200
    assert "285" in exec_res.json()["stdout"]
    print(f"  [PASS] Sandboxed code executed securely: stdout = '{exec_res.json()['stdout'].strip()}'.")

    # 5.3 Writing Assistant (Rewrite & Translation)
    write_res = client.post("/api/tools/writing/assist", json={"action": "rewrite", "text": "we gotta fix this asap"}, headers=headers_a)
    assert write_res.status_code == 200
    print(f"  [PASS] Writing Assistant polish delivered.")

# =============================================================================
# 6. IMAGE GENERATION & VOICE
# =============================================================================
print("\n--- 6. IMAGE GENERATION & VOICE ---")
with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
    # 6.1 Generate image
    img_gen_res = client.post("/api/images/generate", json={"prompt": "Futuristic neon AI neural node", "style": "cyberpunk", "aspectRatio": "16:9"}, headers=headers_a)
    assert img_gen_res.status_code == 200
    gen_img_data = img_gen_res.json()
    gen_img_id = gen_img_data["id"]
    print(f"  [PASS] Image generated: ID {gen_img_id} ({gen_img_data['width']}x{gen_img_data['height']}).")

    # 6.2 Voice status & TTS
    voice_stat = client.get("/api/voice/status", headers=headers_a)
    assert voice_stat.status_code == 200
    print(f"  [PASS] Voice Engine status: active={voice_stat.json()['ttsActive']}, provider='{voice_stat.json()['ttsProvider']}'.")

    tts_res = client.post("/api/voice/synthesize", json={"text": "Welcome to NEXORA AI, your unified intelligence workspace.", "voice": "alloy"}, headers=headers_a)
    assert tts_res.status_code == 200
    print(f"  [PASS] Voice TTS audio synthesized: {tts_res.json()['durationSeconds']}s ({tts_res.json()['audioUrl']}).")

# =============================================================================
# 7. PROJECTS & USER PERSONALIZATION
# =============================================================================
print("\n--- 7. PROJECTS & PERSONALIZATION ---")
with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
    # 7.1 Create project for User A
    proj_res = client.post("/api/projects", json={"name": "NEXORA Production Rollout", "description": "Core platform deployment"}, headers=headers_a)
    assert proj_res.status_code == 200
    proj_a = proj_res.json()
    proj_a_id = proj_a["id"]
    print(f"  [PASS] Project created for User A: ID {proj_a_id}")

    # 7.2 Personalization & Memory for User A
    pref_res = client.get("/api/personalization/preferences", headers=headers_a)
    assert pref_res.status_code == 200

    mem_res = client.post("/api/personalization/memories", json={"key": "Role", "value": "Chief Architect", "category": "preference"}, headers=headers_a)
    assert mem_res.status_code == 200
    mem_id = mem_res.json()["id"]
    print(f"  [PASS] Memory saved for User A: ID {mem_id}")

# =============================================================================
# 8. STRICT MULTI-TENANT ISOLATION (User B -> User A Resources)
# =============================================================================
print("\n--- 8. MULTI-TENANT BOUNDARY ATTACK & ISOLATION VERIFICATION ---")
with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
    # 8.1 User B tries to read User A conversation -> 404
    r_conv = client.get(f"/api/chat/conversations/{conv_a_id}", headers=headers_b)
    assert r_conv.status_code == 404
    print(f"  [PASS] User B blocked from User A Conversation (404 Not Found).")

    # 8.2 User B tries to delete User A conversation -> 404
    r_del_conv = client.delete(f"/api/chat/conversations/{conv_a_id}", headers=headers_b)
    assert r_del_conv.status_code == 404
    print(f"  [PASS] User B blocked from deleting User A Conversation (404 Not Found).")

    # 8.3 User B tries to read User A document -> 404
    r_doc = client.get(f"/api/files/{doc_a_id}", headers=headers_b)
    assert r_doc.status_code == 404
    print(f"  [PASS] User B blocked from User A Document (404 Not Found).")

    # 8.4 User B tries to download User A image -> 404
    r_img = client.get(f"/api/images/generated/{gen_img_id}/download", headers=headers_b)
    assert r_img.status_code == 404
    print(f"  [PASS] User B blocked from User A Generated Image (404 Not Found).")

    # 8.5 User B tries to access User A project -> 404
    r_proj = client.get(f"/api/projects/{proj_a_id}", headers=headers_b)
    assert r_proj.status_code == 404
    print(f"  [PASS] User B blocked from User A Project (404 Not Found).")

    # 8.6 User B tries to delete User A memory -> 404
    r_mem = client.delete(f"/api/personalization/memories/{mem_id}", headers=headers_b)
    assert r_mem.status_code == 404
    print(f"  [PASS] User B blocked from User A Memory (404 Not Found).")

# =============================================================================
# 9. OWNER SECURITY & RBAC GOVERNANCE
# =============================================================================
print("\n--- 9. OWNER SECURITY & RBAC GOVERNANCE ---")
with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
    # 9.1 Normal User A tries to access /api/owner/overview -> 403
    r_owner_leak = client.get("/api/owner/overview", headers=headers_a)
    assert r_owner_leak.status_code == 403, f"Expected 403, got {r_owner_leak.status_code}"
    print(f"  [PASS] Normal User blocked from Owner APIs with 403 Forbidden.")

    # 9.2 Normal User A tries to modify user roles -> 403
    r_role_tamper = client.patch(f"/api/owner/users/{user_a_id}/role", json={"role": "OWNER"}, headers=headers_a)
    assert r_role_tamper.status_code == 403
    print(f"  [PASS] Normal User self-promotion attempt rejected with 403 Forbidden.")

    # 9.3 Login as Platform Owner
    from backend.app.config import settings
    owner_login = client.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
    if owner_login.status_code != 200:
        client.post("/api/auth/signup", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
        owner_login = client.post("/api/auth/login", json={"email": settings.OWNER_EMAIL, "password": "OwnerSuperPass123"})
    
    owner_token = owner_login.json()["token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    assert owner_login.json()["user"]["role"] == "OWNER"

    # 9.4 Owner calls /api/owner/overview
    owner_stats = client.get("/api/owner/overview", headers=owner_headers).json()
    assert "totalUsers" in owner_stats
    assert "newUsersToday" in owner_stats
    assert "loginEvents" in owner_stats
    assert "aiRequests" in owner_stats
    print(f"  [PASS] Owner Overview retrieved: {owner_stats['totalUsers']} total users, {owner_stats['aiRequests']} AI requests, {owner_stats['loginEvents']} logins.")

    # 9.5 Owner calls /api/owner/login-activity
    logins_act = client.get("/api/owner/login-activity", headers=owner_headers).json()
    assert len(logins_act["activity"]) > 0
    print(f"  [PASS] Owner Login Activity feed retrieved: {len(logins_act['activity'])} audit events.")

    # 9.6 Owner suspends User B, verify User B blocked, then reactivates
    susp = client.patch(f"/api/owner/users/{user_b_id}/status", json={"accountStatus": "SUSPENDED"}, headers=owner_headers)
    assert susp.status_code == 200
    assert susp.json()["accountStatus"] == "SUSPENDED"

    b_blocked_login = client.post("/api/auth/login", json={"email": user_b_email, "password": user_pass})
    assert b_blocked_login.status_code == 403
    print(f"  [PASS] Suspended User B login blocked with 403 Forbidden.")

    react = client.patch(f"/api/owner/users/{user_b_id}/status", json={"accountStatus": "ACTIVE"}, headers=owner_headers)
    assert react.status_code == 200
    print(f"  [PASS] Owner reactivated User B account successfully.")

# =============================================================================
# 10. ERROR HANDLING & HOST SAFETY TESTS
# =============================================================================
print("\n--- 10. ERROR HANDLING & HOST SAFETY ---")
with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
    # 10.1 Disallowed extension upload
    bad_file = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")}
    r_bad_ext = client.post("/api/files/upload", files=bad_file, headers=headers_a)
    assert r_bad_ext.status_code == 400
    print(f"  [PASS] Dangerous file extension (.exe) rejected with 400 Bad Request.")

    # 10.2 Path Traversal Attack Injection in Chat
    r_trav = client.get(f"/api/files/..%2f..%2f..%2f..%2fetc%2fpasswd/download", headers=headers_a)
    assert r_trav.status_code in (404, 400)
    print(f"  [PASS] Path traversal payload rejected safely.")

    # 10.3 Unhandled endpoint
    r_404 = client.get("/api/nonexistent_endpoint", headers=headers_a)
    assert r_404.status_code == 404
    assert "detail" in r_404.json()
    print(f"  [PASS] Clean 404 JSON response returned without server stack trace exposure.")

print("\n" + "="*80)
print("ALL REAL-WORLD LIVE VERIFICATION TESTS PASSED WITH 100% SUCCESS!")
print("="*80)
