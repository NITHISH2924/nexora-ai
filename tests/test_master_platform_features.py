import pytest
import re
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings
from backend.app.services.ai_providers.manager import ai_manager
from backend.app.services.voice_service import voice_service
from backend.app.security import create_access_token

@pytest.mark.asyncio
async def test_intelligent_ai_model_router():
    """Verify Phase 2 Intelligent AI Model Router task classification and model dispatch."""
    # 1. Models list includes Smart Router as top option
    models = ai_manager.list_models()
    assert len(models) > 0
    assert models[0]["id"] == "nexora-smart-router"
    assert "Smart Router" in models[0]["category"]

    # 2. Classification checks
    coding_res = ai_manager.classify_task("Write a Python function to solve binary search tree traversal")
    assert coding_res["taskType"] == "coding"

    vision_res = ai_manager.classify_task("Analyze this diagram and describe the picture", has_images=True)
    assert vision_res["taskType"] == "vision"

    search_res = ai_manager.classify_task("What are the latest news headlines today in 2026?")
    assert search_res["taskType"] == "search"

    reasoning_res = ai_manager.classify_task("Provide a step-by-step proof and analyze the trade-offs of Byzantine Fault Tolerance")
    assert reasoning_res["taskType"] == "reasoning"

    simple_res = ai_manager.classify_task("Hello! Who are you?")
    assert simple_res["taskType"] == "simple"

    # 3. Resolve provider and model via Smart Router
    p, m = ai_manager.resolve_provider_and_model(
        requested_model="nexora-smart-router",
        prompt="def quicksort(arr): return arr"
    )
    assert p is not None
    assert m is not None

@pytest.mark.asyncio
async def test_personalized_voice_greetings_dynamic_users():
    """Verify Phase 5 personalized greeting for different user names and fallback."""
    # User 1: Nithish Kumar R -> "Yes, Nithish? I'm listening."
    g1, name1 = voice_service.format_personalized_greeting("Nithish Kumar R")
    assert g1 == "Yes, Nithish? I'm listening."
    assert name1 == "Nithish"

    # User 2: Arun -> "Yes, Arun? I'm listening."
    g2, name2 = voice_service.format_personalized_greeting("Arun")
    assert g2 == "Yes, Arun? I'm listening."
    assert name2 == "Arun"

    # User 3: Priya Sharma -> "Yes, Priya? I'm listening."
    g3, name3 = voice_service.format_personalized_greeting("Priya Sharma")
    assert g3 == "Yes, Priya? I'm listening."
    assert name3 == "Priya"

    # Empty / Missing profile name -> "Yes, I'm listening."
    g_empty, name_empty = voice_service.format_personalized_greeting("")
    assert g_empty == "Yes, I'm listening."
    assert name_empty is None

    g_none, name_none = voice_service.format_personalized_greeting(None)
    assert g_none == "Yes, I'm listening."
    assert name_none is None

@pytest.mark.asyncio
async def test_voice_wake_greet_http_endpoint():
    """Verify POST /api/voice/wake-greet dynamically returns personal greeting based on account."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user Arun
        email_arun = f"arun_{id(object())}@test.com"
        reg_res = await client.post("/api/auth/signup", json={
            "email": email_arun,
            "password": "Password123!",
            "fullName": "Arun Kumar"
        })
        assert reg_res.status_code == 200
        user_arun = reg_res.json()["user"]

        token_arun = create_access_token(data={"sub": user_arun["userId"], "email": email_arun, "role": "USER"})
        
        # Call /api/voice/wake-greet
        greet_res = await client.post(
            "/api/voice/wake-greet",
            headers={"Authorization": f"Bearer {token_arun}"},
            json={"voice": "onyx"}
        )
        assert greet_res.status_code == 200
        greet_data = greet_res.json()
        assert greet_data["greetingText"] == "Yes, Arun? I'm listening."
        assert greet_data["userName"] == "Arun"
        assert "audioUrl" in greet_data
        assert greet_data["voice"] == "onyx"

@pytest.mark.asyncio
async def test_owner_only_dashboard_security_and_health():
    """Verify Phase 7 owner dashboard authorization and system health."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Non-owner user is forbidden
        user_email = f"standard_{id(object())}@test.com"
        reg = await client.post("/api/auth/signup", json={
            "email": user_email,
            "password": "Password123!",
            "fullName": "Standard User"
        })
        user_id = reg.json()["user"]["userId"]
        user_token = create_access_token(data={"sub": user_id, "email": user_email, "role": "USER"})

        overview_forbidden = await client.get("/api/owner/overview", headers={"Authorization": f"Bearer {user_token}"})
        assert overview_forbidden.status_code == 403

        health_forbidden = await client.get("/api/owner/system-health", headers={"Authorization": f"Bearer {user_token}"})
        assert health_forbidden.status_code == 403

        # 2. Owner user is authorized
        owner_email = f"owner_{id(object())}@nexora.ai"
        reg_owner = await client.post("/api/auth/signup", json={
            "email": owner_email,
            "password": "Password123!",
            "fullName": settings.OWNER_NAME
        })
        owner_id = reg_owner.json()["user"]["userId"]

        # Promote to OWNER in DB
        from backend.app.database import get_db
        async with get_db() as db:
            await db.execute("UPDATE users SET role = 'OWNER' WHERE userId = ?", (owner_id,))
            await db.commit()

        owner_token = create_access_token(data={"sub": owner_id, "email": owner_email, "role": "OWNER"})

        # Owner overview succeeds
        overview_res = await client.get("/api/owner/overview", headers={"Authorization": f"Bearer {owner_token}"})
        assert overview_res.status_code == 200
        overview_data = overview_res.json()
        assert overview_data["ownerName"] == "Nithish Kumar R"
        assert overview_data["totalUsers"] >= 2

        # Owner system-health succeeds
        health_res = await client.get("/api/owner/system-health", headers={"Authorization": f"Bearer {owner_token}"})
        assert health_res.status_code == 200
        health_data = health_res.json()
        assert health_data["status"] == "HEALTHY"
        assert health_data["displayTimezone"] == "Asia/Kolkata (IST)"
        assert "providers" in health_data

@pytest.mark.asyncio
async def test_leadership_identity_accuracy():
    """Verify Phase 8 verbatim leadership response: 'The Owner is Nithish Kumar R and the CEO is Dhanushiya S.'"""
    content, _ = await ai_manager.generate_response(
        messages=[{"role": "user", "content": "Who is the owner and CEO of NEXORA AI?"}],
        model="nexora-smart-router"
    )
    assert content == "The Owner is Nithish Kumar R and the CEO is Dhanushiya S."

@pytest.mark.asyncio
async def test_video_and_learning_tools():
    """Verify Phase 4 AI Video Studio and Learning Hub tools."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user
        email = f"tools_{id(object())}@test.com"
        reg = await client.post("/api/auth/signup", json={"email": email, "password": "Password123!", "fullName": "Tool Tester"})
        token = create_access_token(data={"sub": reg.json()["user"]["userId"], "email": email, "role": "USER"})

        # Video plan
        v_res = await client.post("/api/tools/video/plan", headers={"Authorization": f"Bearer {token}"}, json={
            "topic": "Autonomous Mars Rover Exploration",
            "style": "cinematic",
            "durationSeconds": 60,
            "targetAudience": "Space exploration enthusiasts"
        })
        assert v_res.status_code == 200
        v_data = v_res.json()
        assert len(v_data["scenes"]) == 4
        assert v_data["externalProviderRequired"] is True
        assert "audioScript" in v_data

        # Learning assist
        l_res = await client.post("/api/tools/learning/assist", headers={"Authorization": f"Bearer {token}"}, json={
            "action": "quiz",
            "topic": "Python Asyncio and Event Loops",
            "level": "intermediate",
            "questionCount": 5
        })
        assert l_res.status_code == 200
        l_data = l_res.json()
        assert l_data["action"] == "quiz"
        assert len(l_data["content"]) > 20
