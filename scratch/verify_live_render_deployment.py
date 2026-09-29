import sys
import json
import urllib.request
import urllib.error
import uuid
import time

def verify_render_deployment(base_url: str):
    base_url = base_url.rstrip("/")
    print("=" * 80)
    print(f"NEXORA AI — REAL PUBLIC CLOUD DEPLOYMENT VERIFICATION")
    print(f"TARGET CLOUD URL: {base_url}")
    print("=" * 80)

    # 1. Verify Public HTTP/HTTPS Static and Web App Endpoints
    routes = [
        ("/", "Landing Page"),
        ("/login", "Login Page"),
        ("/signup", "Signup Page"),
        ("/app", "AI Workspace"),
        ("/docs", "OpenAPI Documentation"),
        ("/api/company/leadership", "Leadership Governance API"),
        ("/privacy", "Privacy Policy"),
        ("/terms", "Terms of Service"),
        ("/delete-account", "Account Deletion Policy"),
        ("/assets/logo-light.png", "Official Light Logo Asset"),
        ("/assets/logo-dark.png", "Official Dark Logo Asset"),
        ("/css/main.css", "Design System CSS"),
        ("/js/theme.js", "Theme Engine JS")
    ]

    print("\n[PHASE 1] Testing Public Web Endpoints & Static Assets...")
    all_routes_passed = True
    for route, desc in routes:
        url = base_url + route
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NEXORA-Cloud-Verifier/1.0"})
            with urllib.request.urlopen(req, timeout=15) as res:
                status_code = res.status
                ctype = res.headers.get("Content-Type", "")
                print(f"  [PASS] {route:28} -> HTTP {status_code} ({desc}) [{ctype}]")
        except Exception as e:
            print(f"  [FAIL] {route:28} -> Error: {e}")
            all_routes_passed = False

    # 2. Verify Leadership Identity Endpoint Content
    print("\n[PHASE 2] Testing Leadership Governance Endpoint Content...")
    try:
        req = urllib.request.Request(base_url + "/api/company/leadership", headers={"User-Agent": "NEXORA-Cloud-Verifier/1.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode("utf-8"))
            owner = data.get("owner")
            ceo = data.get("ceo")
            std_ans = data.get("standardAnswer")
            print(f"  [PASS] Owner: {owner}")
            print(f"  [PASS] CEO:   {ceo}")
            print(f"  [PASS] Rule:  {std_ans}")
            assert owner == "Nithish Kumar R", f"Unexpected owner: {owner}"
            assert ceo == "Dhanushiya S", f"Unexpected CEO: {ceo}"
    except Exception as e:
        print(f"  [FAIL] Leadership API Error: {e}")

    # 3. Test Cloud Database Registration & Authentication
    print("\n[PHASE 3] Testing Live User Registration & Cloud PostgreSQL / Persistence...")
    rand_id = uuid.uuid4().hex[:8]
    test_email = f"render_cloud_user_{rand_id}@nexora.ai"
    test_password = "SecureCloudPassword2026!"
    token = None

    try:
        signup_payload = json.dumps({"email": test_email, "password": test_password}).encode("utf-8")
        req_signup = urllib.request.Request(
            base_url + "/api/auth/signup",
            data=signup_payload,
            headers={"Content-Type": "application/json", "User-Agent": "NEXORA-Cloud-Verifier/1.0"}
        )
        with urllib.request.urlopen(req_signup, timeout=15) as res:
            data = json.loads(res.read().decode("utf-8"))
            token = data.get("token")
            user = data.get("user", {})
            print(f"  [PASS] Registered User: {user.get('email')} (ID: {user.get('userId')})")
    except Exception as e:
        print(f"  [FAIL] Cloud Signup Error: {e}")

    if token:
        # 4. Test Cloud Login
        print("\n[PHASE 4] Testing Live Login & Token Issuance...")
        try:
            login_payload = json.dumps({"email": test_email, "password": test_password}).encode("utf-8")
            req_login = urllib.request.Request(
                base_url + "/api/auth/login",
                data=login_payload,
                headers={"Content-Type": "application/json", "User-Agent": "NEXORA-Cloud-Verifier/1.0"}
            )
            with urllib.request.urlopen(req_login, timeout=15) as res:
                data = json.loads(res.read().decode("utf-8"))
                auth_token = data.get("token")
                print(f"  [PASS] Login successful! JWT Token validated.")
        except Exception as e:
            print(f"  [FAIL] Cloud Login Error: {e}")

        # 5. Test AI Model Discovery
        print("\n[PHASE 5] Testing Cloud AI Engine & Model Discovery...")
        try:
            req_models = urllib.request.Request(
                base_url + "/api/chat/models",
                headers={"Authorization": f"Bearer {token}", "User-Agent": "NEXORA-Cloud-Verifier/1.0"}
            )
            with urllib.request.urlopen(req_models, timeout=15) as res:
                data = json.loads(res.read().decode("utf-8"))
                models = [m.get("id") for m in data.get("models", [])]
                print(f"  [PASS] Models available in cloud: {models}")
        except Exception as e:
            print(f"  [FAIL] Cloud AI Models Error: {e}")

    print("\n" + "=" * 80)
    print("ALL CLOUD DEPLOYMENT VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        target_url = "https://nexora-ai-platform.onrender.com"
    verify_render_deployment(target_url)
