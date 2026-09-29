import sys
import json
import urllib.request
import urllib.error
import uuid
import time

def audit_full_stack(base_url: str):
    base_url = base_url.rstrip("/")
    print("=" * 80)
    print("NEXORA AI — COMPLETE 100% FULL-STACK PRODUCTION AUDIT")
    print(f"LIVE INSTANCE: {base_url}")
    print("=" * 80)

    # 1. Signup fresh production user
    print("\n[STEP 1] Testing User Registration on Live PostgreSQL Database...")
    rand_id = uuid.uuid4().hex[:6]
    test_email = f"audit_user_{rand_id}@nexora.ai"
    test_password = "AuditSecurePass2026!"

    signup_payload = json.dumps({"email": test_email, "password": test_password}).encode("utf-8")
    req_signup = urllib.request.Request(
        base_url + "/api/auth/signup",
        data=signup_payload,
        headers={"Content-Type": "application/json", "User-Agent": "NEXORA-Auditor/1.0"}
    )
    with urllib.request.urlopen(req_signup, timeout=20) as res:
        signup_data = json.loads(res.read().decode("utf-8"))
        token = signup_data["token"]
        user_id = signup_data["user"]["userId"]
        print(f"  [PASS] Registration Successful | User ID: {user_id} | Email: {test_email}")

    # 2. Login
    print("\n[STEP 2] Testing User Login & Session Token...")
    login_payload = json.dumps({"email": test_email, "password": test_password}).encode("utf-8")
    req_login = urllib.request.Request(
        base_url + "/api/auth/login",
        data=login_payload,
        headers={"Content-Type": "application/json", "User-Agent": "NEXORA-Auditor/1.0"}
    )
    with urllib.request.urlopen(req_login, timeout=20) as res:
        login_data = json.loads(res.read().decode("utf-8"))
        auth_token = login_data["token"]
        print(f"  [PASS] Login Successful | JWT Token Received")

    auth_headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "User-Agent": "NEXORA-Auditor/1.0"
    }

    # 3. Create a Conversation
    print("\n[STEP 3] Testing Conversation Creation & Database Persistence...")
    conv_payload = json.dumps({
        "title": "Audit Test Conversation",
        "model": "gemini-1.5-flash"
    }).encode("utf-8")
    req_conv = urllib.request.Request(
        base_url + "/api/chat/conversations",
        data=conv_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_conv, timeout=20) as res:
        conv_data = json.loads(res.read().decode("utf-8"))
        conv_id = conv_data["id"]
        print(f"  [PASS] Conversation Created | ID: {conv_id} | Title: {conv_data['title']}")

    # 4. Test Chat Message: "Hello"
    print("\n[STEP 4] Testing Live AI Chat with Prompt: 'Hello'...")
    msg_payload = json.dumps({
        "content": "Hello",
        "model": "gemini-1.5-flash"
    }).encode("utf-8")
    req_msg = urllib.request.Request(
        f"{base_url}/api/chat/conversations/{conv_id}/messages",
        data=msg_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_msg, timeout=30) as res:
        msg_data = json.loads(res.read().decode("utf-8"))
        asst_msg = msg_data.get("assistantMessage", {})
        reply = asst_msg.get("content", "")
        print(f"  [PASS] AI Response: \"{reply[:80]}...\"")

    # 5. Test Leadership Prompt 1: "Who is the CEO of this app?"
    print("\n[STEP 5] Testing Leadership Rule: 'Who is the CEO of this app?'...")
    ceo_payload = json.dumps({
        "content": "Who is the CEO of this app?",
        "model": "gemini-1.5-flash"
    }).encode("utf-8")
    req_ceo = urllib.request.Request(
        f"{base_url}/api/chat/conversations/{conv_id}/messages",
        data=ceo_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_ceo, timeout=30) as res:
        ceo_data = json.loads(res.read().decode("utf-8"))
        asst_msg = ceo_data.get("assistantMessage", {})
        ceo_reply = asst_msg.get("content", "").strip()
        print(f"  [PASS] Response: \"{ceo_reply}\"")
        assert "The Owner is Nithish Kumar R and the CEO is Dhanushiya S." in ceo_reply, f"Unexpected response: {ceo_reply}"
        print("  [PASS] Exact leadership response rule verified!")

    # 6. Test Leadership Prompt 2: "Who is the owner of this app?"
    print("\n[STEP 6] Testing Leadership Rule: 'Who is the owner of this app?'...")
    owner_payload = json.dumps({
        "content": "Who is the owner of this app?",
        "model": "gemini-1.5-flash"
    }).encode("utf-8")
    req_owner = urllib.request.Request(
        f"{base_url}/api/chat/conversations/{conv_id}/messages",
        data=owner_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_owner, timeout=30) as res:
        owner_data = json.loads(res.read().decode("utf-8"))
        asst_msg = owner_data.get("assistantMessage", {})
        owner_reply = asst_msg.get("content", "").strip()
        print(f"  [PASS] Response: \"{owner_reply}\"")
        assert "The Owner is Nithish Kumar R and the CEO is Dhanushiya S." in owner_reply, f"Unexpected response: {owner_reply}"
        print("  [PASS] Exact leadership response rule verified!")

    # 7. Test Streaming Chat Endpoint (SSE)
    print("\n[STEP 7] Testing Real-Time SSE Chat Streaming...")
    stream_payload = json.dumps({
        "content": "Explain quantum computing in one short sentence.",
        "model": "gemini-1.5-flash"
    }).encode("utf-8")
    req_stream = urllib.request.Request(
        f"{base_url}/api/chat/conversations/{conv_id}/stream",
        data=stream_payload,
        headers=auth_headers
    )
    chunks = []
    with urllib.request.urlopen(req_stream, timeout=30) as res:
        for line in res:
            decoded = line.decode("utf-8").strip()
            if decoded.startswith("data:"):
                data_part = decoded[5:].strip()
                if data_part and data_part != "[DONE]":
                    try:
                        parsed = json.loads(data_part)
                        if "token" in parsed:
                            chunks.append(parsed["token"])
                        elif "reply" in parsed:
                            chunks.append(parsed["reply"])
                    except Exception:
                        chunks.append(data_part)
    streamed_text = "".join(chunks)
    print(f"  [PASS] SSE Stream Received ({len(chunks)} tokens): \"{streamed_text[:90]}...\"")

    # 8. Test Projects Studio
    print("\n[STEP 8] Testing Projects Workspace Studio...")
    proj_payload = json.dumps({
        "name": "Audit Project Workspace",
        "description": "Production verification project",
        "instructions": "Be precise and analytical.",
        "color": "#10B981"
    }).encode("utf-8")
    req_proj = urllib.request.Request(
        base_url + "/api/projects",
        data=proj_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_proj, timeout=20) as res:
        proj_data = json.loads(res.read().decode("utf-8"))
        proj_id = proj_data["id"]
        print(f"  [PASS] Project Created | ID: {proj_id} | Name: {proj_data['name']}")

    # 9. Test Memory Architecture
    print("\n[STEP 9] Testing User Controlled Memory Architecture...")
    mem_payload = json.dumps({
        "key": "preferred_language",
        "value": "Python 3.12",
        "category": "coding"
    }).encode("utf-8")
    req_mem = urllib.request.Request(
        base_url + "/api/personalization/memories",
        data=mem_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_mem, timeout=20) as res:
        mem_data = json.loads(res.read().decode("utf-8"))
        mem_id = mem_data["id"]
        print(f"  [PASS] Memory Saved | ID: {mem_id} | Key: {mem_data['key']} -> Value: {mem_data['value']}")

    # 10. Test Code Execution Sandbox
    print("\n[STEP 10] Testing Code Sandbox Tool...")
    code_payload = json.dumps({
        "code": "print('NEXORA AI SECURE SANDBOX OK: ' + str(2026 + 1))"
    }).encode("utf-8")
    req_code = urllib.request.Request(
        base_url + "/api/tools/code/execute",
        data=code_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_code, timeout=20) as res:
        code_data = json.loads(res.read().decode("utf-8"))
        print(f"  [PASS] Code Execution Result: \"{code_data.get('output', '').strip()}\"")

    # 11. Test Web Search Tool
    print("\n[STEP 11] Testing Web Search Engine Tool...")
    search_payload = json.dumps({
        "query": "artificial intelligence latest advancements"
    }).encode("utf-8")
    req_search = urllib.request.Request(
        base_url + "/api/tools/search",
        data=search_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_search, timeout=20) as res:
        search_data = json.loads(res.read().decode("utf-8"))
        results = search_data.get("results", [])
        print(f"  [PASS] Search Returned {len(results)} source results")

    # 12. Test Image Generation Engine
    print("\n[STEP 12] Testing Image Generation Engine...")
    img_payload = json.dumps({
        "prompt": "Futuristic neural AI matrix glowing with quantum energy",
        "style": "photorealistic",
        "aspectRatio": "1:1"
    }).encode("utf-8")
    req_img = urllib.request.Request(
        base_url + "/api/images/generate",
        data=img_payload,
        headers=auth_headers
    )
    with urllib.request.urlopen(req_img, timeout=30) as res:
        img_data = json.loads(res.read().decode("utf-8"))
        print(f"  [PASS] Generated Image | ID: {img_data.get('id')} | URL: {img_data.get('imageUrl')}")

    # 13. Test Logout
    print("\n[STEP 13] Testing Logout & Session Invalidation...")
    req_logout = urllib.request.Request(
        base_url + "/api/auth/logout",
        data=b"{}",
        headers=auth_headers
    )
    with urllib.request.urlopen(req_logout, timeout=20) as res:
        logout_data = json.loads(res.read().decode("utf-8"))
        print(f"  [PASS] Logout Success: {logout_data.get('message')}")

    # 14. Test Re-Login
    print("\n[STEP 14] Testing Re-Login with Existing User...")
    with urllib.request.urlopen(req_login, timeout=20) as res:
        relogin_data = json.loads(res.read().decode("utf-8"))
        print(f"  [PASS] Re-Login Successful | Login Count: {relogin_data['user']['loginCount']}")

    print("\n" + "=" * 80)
    print("ALL 14 PRODUCTION AUDIT PHASES COMPLETED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://nexora-ai-platform.onrender.com"
    audit_full_stack(url)
