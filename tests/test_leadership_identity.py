import os
import sys
import uuid
import pytest
import asyncio
from pathlib import Path
from starlette.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException
from backend.app.config import settings, is_leadership_query
from backend.app.main import app
from backend.app.database import create_tables, get_db
from backend.app.services.user_service import user_service
from backend.app.services.ai_providers.manager import ai_manager
from backend.app.models import UserRegisterRequest, UserLoginRequest


EXPECTED_LEADERSHIP_RESPONSE = "The Owner is Nithish Kumar R and the CEO is Dhanushiya S."

LEADERSHIP_QUERIES = [
    "Who is the Owner?",
    "Who is the CEO?",
    "Who owns NEXORA AI?",
    "Who is the CEO of NEXORA AI?",
    "Who created NEXORA AI?",
    "Tell me about the leadership of NEXORA AI.",
    "Who is the owner?",
    "Who is the ceo?",
    "Who is owner?",
    "Who is ceo?",
    "Who owns NEXORA?",
    "Who created this platform?",
    "Who is the founder of NEXORA AI?",
    "Tell me about the leadership of nexora",
    "Who is your owner?",
    "Who is your CEO?"
]


@pytest.mark.asyncio
async def test_leadership_identity_and_response_rule():
    """
    Comprehensive verification for NEXORA AI Official Leadership Identity:
    1. Roles: OWNER -> Nithish Kumar R, CEO -> Dhanushiya S
    2. Response Rule: Any question related to Owner OR CEO must return:
       'The Owner is Nithish Kumar R and the CEO is Dhanushiya S.'
    3. Both streaming and non-streaming responses contain the exact leadership rule.
    4. RBAC protection: Normal users get 403, Owner & CEO get full leadership access.
    5. Public Company Leadership Endpoint returns verified identity.
    """
    print("\n" + "="*80)
    print("RUNNING OFFICIAL LEADERSHIP IDENTITY & RBAC TEST SUITE")
    print(f"[*] OWNER: {settings.OWNER_NAME}")
    print(f"[*] CEO:   {settings.CEO_NAME}")
    print(f"[*] STANDARD ANSWER: \"{EXPECTED_LEADERSHIP_RESPONSE}\"")
    print("="*80 + "\n")

    # 1. Database Initialization
    await create_tables()
    print("[1] Database initialized.")

    # 2. Config & Constant Verification
    assert settings.OWNER_NAME == "Nithish Kumar R", f"Expected Owner 'Nithish Kumar R', got '{settings.OWNER_NAME}'"
    assert settings.CEO_NAME == "Dhanushiya S", f"Expected CEO 'Dhanushiya S', got '{settings.CEO_NAME}'"
    assert settings.LEADERSHIP_RESPONSE == EXPECTED_LEADERSHIP_RESPONSE
    print("    [PASS] Config constants correctly set to Nithish Kumar R (Owner) and Dhanushiya S (CEO).")

    # 3. Test Detection Function
    print("\n[2] Testing is_leadership_query() detection logic...")
    for q in LEADERSHIP_QUERIES:
        assert is_leadership_query(q) is True, f"Failed to detect leadership query: '{q}'"
    
    # Negative checks (ensure no false positives on normal queries)
    normal_queries = [
        "Write a Python FastAPI async endpoint",
        "Explain transformer self-attention mechanisms",
        "Analyze this CSV sales data for quarterly trends",
        "Translate this paragraph into French"
    ]
    for nq in normal_queries:
        assert is_leadership_query(nq) is False, f"False positive leadership trigger for: '{nq}'"
    print(f"    [PASS] Successfully detected all {len(LEADERSHIP_QUERIES)} leadership query variations with zero false positives.")

    # 4. Test AI Manager Direct Response Generation
    print("\n[3] Testing AI Manager generate_response() for all leadership prompts...")
    for query in LEADERSHIP_QUERIES:
        messages = [{"role": "user", "content": query}]
        response_text, model_used = await ai_manager.generate_response(messages=messages)
        assert response_text == EXPECTED_LEADERSHIP_RESPONSE, (
            f"Query: '{query}'\nExpected: '{EXPECTED_LEADERSHIP_RESPONSE}'\nGot: '{response_text}'"
        )
        assert "Nithish Kumar R" in response_text
        assert "Dhanushiya S" in response_text
        assert "Owner" in response_text
        assert "CEO" in response_text
    print(f"    [PASS] All {len(LEADERSHIP_QUERIES)} queries generated the exact mandatory leadership response.")

    # 5. Test Streaming Response Chunks
    print("\n[4] Testing AI Manager stream_response() for leadership prompts...")
    test_stream_queries = [
        "Who is the Owner?",
        "Who is the CEO?",
        "Who owns NEXORA AI?",
        "Who is the CEO of NEXORA AI?"
    ]
    for query in test_stream_queries:
        messages = [{"role": "user", "content": query}]
        chunks = []
        async for chunk in ai_manager.stream_response(messages=messages):
            chunks.append(chunk)
        streamed_full = "".join(chunks)
        assert streamed_full == EXPECTED_LEADERSHIP_RESPONSE, (
            f"Streaming Query: '{query}'\nExpected: '{EXPECTED_LEADERSHIP_RESPONSE}'\nGot: '{streamed_full}'"
        )
    print("    [PASS] Streaming engine yields the exact combined leadership response.")

    # 6. Test Public Company Leadership API
    print("\n[5] Testing Public GET /api/company/leadership endpoint...")
    client = TestClient(app, base_url="http://127.0.0.1:8000")
    resp = client.get("/api/company/leadership")
    assert resp.status_code == 200, f"Leadership endpoint failed: {resp.status_code}"
    lead_data = resp.json()
    assert lead_data["company"] == "NEXORA AI"
    assert lead_data["owner"] == "Nithish Kumar R"
    assert lead_data["ceo"] == "Dhanushiya S"
    assert lead_data["standardAnswer"] == EXPECTED_LEADERSHIP_RESPONSE
    print(f"    [PASS] Public API returned: Owner={lead_data['owner']}, CEO={lead_data['ceo']}")

    # 7. Test RBAC Isolation & Leadership Roles
    print("\n[6] Testing RBAC: Normal User vs Owner vs CEO Privileges...")
    
    # 7.1 Normal User Registration
    rand_suffix = uuid.uuid4().hex[:6]
    normal_email = f"standard_user_{rand_suffix}@example.com"
    normal_user, normal_token = await user_service.register_user(
        UserRegisterRequest(email=normal_email, password="SecureUserPass123!")
    )
    assert normal_user["role"] == "USER", f"Expected role USER, got {normal_user['role']}"
    normal_headers = {"Authorization": f"Bearer {normal_token}"}

    # Normal user must be FORBIDDEN from Owner Console
    forbidden_res = client.get("/api/owner/overview", headers=normal_headers)
    assert forbidden_res.status_code == 403, f"Normal user should get 403 Forbidden, got {forbidden_res.status_code}"
    print("    [PASS] Normal user strictly blocked from /api/owner/* with 403 Forbidden.")

    # 7.2 Platform Owner Registration / Token
    try:
        owner_user, owner_token = await user_service.register_user(
            UserRegisterRequest(email=settings.OWNER_EMAIL, password="OwnerSecretPassword123!")
        )
    except HTTPException as e:
        if e.status_code == 409:
            owner_user = await user_service.get_user_by_email(settings.OWNER_EMAIL)
            from backend.app.security import create_access_token
            owner_token = create_access_token({"sub": owner_user["userId"], "email": settings.OWNER_EMAIL, "role": "OWNER"})
        else:
            raise
    assert owner_user["role"] == "OWNER", f"Expected OWNER role for {settings.OWNER_EMAIL}, got {owner_user['role']}"
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Owner access to /api/owner/overview
    owner_res = client.get("/api/owner/overview", headers=owner_headers)
    assert owner_res.status_code == 200, f"Owner should have 200 OK, got {owner_res.status_code}"
    overview_stats = owner_res.json()
    assert overview_stats["ownerName"] == "Nithish Kumar R"
    assert overview_stats["ceoName"] == "Dhanushiya S"
    print(f"    [PASS] Platform Owner ({settings.OWNER_EMAIL}) granted administrative access (Role: OWNER).")

    # 7.3 CEO Registration / Token
    try:
        ceo_user, ceo_token = await user_service.register_user(
            UserRegisterRequest(email=settings.CEO_EMAIL, password="CeoSecretPassword123!")
        )
    except HTTPException as e:
        if e.status_code == 409:
            ceo_user = await user_service.get_user_by_email(settings.CEO_EMAIL)
            from backend.app.security import create_access_token
            ceo_token = create_access_token({"sub": ceo_user["userId"], "email": settings.CEO_EMAIL, "role": "CEO"})
        else:
            raise
    assert ceo_user["role"] == "CEO", f"Expected CEO role for {settings.CEO_EMAIL}, got {ceo_user['role']}"
    ceo_headers = {"Authorization": f"Bearer {ceo_token}"}

    # CEO access to /api/owner/overview
    ceo_res = client.get("/api/owner/overview", headers=ceo_headers)
    assert ceo_res.status_code == 200, f"CEO should have 200 OK, got {ceo_res.status_code}"
    print(f"    [PASS] Platform CEO ({settings.CEO_EMAIL}) granted executive access (Role: CEO).")

    print("\n" + "="*80)
    print("ALL LEADERSHIP IDENTITY & RBAC TESTS PASSED SUCCESSFULLY!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_leadership_identity_and_response_rule())
