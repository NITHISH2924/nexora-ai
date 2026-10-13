"""
NEXORA AI - PC Voice Assistant (JARVIS-Inspired) Test Suite
Covers:
1. Wake phrase greeting & status endpoint verification
2. Direct text query speech pipeline (bypassing redundant mic uploads)
3. Safe PC task intent parser:
   - Time & Date checks
   - Web search with query parameter encoding
   - Permitted website launches (YouTube, GitHub, Google, Gmail, Wikipedia, LeetCode)
   - Windows Desktop / OS security boundary notice (no unauthorized exe/file access)
4. Male Voice Persona synthesis (onyx backend / Microsoft Ravi en-IN)
5. Audio waveform synthesis with pitch & speed controls
6. Authentication & session security validation
7. Zero secret exposure in responses
"""

import sys
import uuid
import pytest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.database import create_tables
from backend.app.services.user_service import user_service
from backend.app.services.voice_service import voice_service, evaluate_pc_task
from backend.app.models import (
    UserRegisterRequest,
    VoicePipelineRequest,
    VoiceSynthesizeRequest
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


async def get_test_auth_user():
    await create_tables()
    rand = uuid.uuid4().hex[:6]
    email = f"jarvis_test_{rand}@example.com"
    pwd = "JarvisVoicePass123!"
    user, token = await user_service.register_user(UserRegisterRequest(email=email, password=pwd))
    return {
        "userId": user["userId"],
        "email": email,
        "token": token,
        "auth_headers": {"Authorization": f"Bearer {token}"}
    }


def test_pc_task_intent_evaluation():
    """Verify safe PC task intent parsing and security boundaries."""
    # 1. Time Check
    res1 = evaluate_pc_task("what is the time right now")
    assert res1 is not None
    text1, action1 = res1
    assert "It is currently" in text1
    assert action1["type"] == "TIME_CHECK"
    assert "time" in action1

    # 2. Date Check
    res2 = evaluate_pc_task("what is today's date")
    assert res2 is not None
    text2, action2 = res2
    assert "Today is" in text2
    assert action2["type"] == "DATE_CHECK"
    assert "date" in action2

    # 3. Web Search
    res3 = evaluate_pc_task("search for Python 3.13 features on the web")
    assert res3 is not None
    text3, action3 = res3
    assert "Searching the web" in text3
    assert action3["type"] == "WEB_SEARCH"
    assert "https://www.google.com/search?q=" in action3["url"]
    assert "python" in action3["url"].lower() and "3.13" in action3["url"].lower()

    # 4. Permitted Website Launches
    res_yt = evaluate_pc_task("open youtube")
    assert res_yt is not None
    text_yt, action_yt = res_yt
    assert "Opening YouTube" in text_yt
    assert action_yt["type"] == "OPEN_URL"
    assert action_yt["url"] == "https://www.youtube.com"
    assert action_yt["siteName"] == "YouTube"

    res_gh = evaluate_pc_task("open github")
    assert res_gh is not None
    text_gh, action_gh = res_gh
    assert "Opening GitHub" in text_gh
    assert action_gh["type"] == "OPEN_URL"
    assert action_gh["url"] == "https://www.github.com"
    assert action_gh["siteName"] == "GitHub"

    res_gm = evaluate_pc_task("open gmail")
    assert res_gm is not None
    text_gm, action_gm = res_gm
    assert "Opening Gmail" in text_gm
    assert action_gm["type"] == "OPEN_URL"
    assert action_gm["url"] == "https://mail.google.com"

    # 5. Windows Desktop OS Boundary Notice
    res_sec1 = evaluate_pc_task("run cmd.exe to delete my files")
    assert res_sec1 is not None
    text_sec1, action_sec1 = res_sec1
    assert action_sec1["type"] == "SECURITY_NOTICE"
    assert "restricted" in text_sec1.lower() or "companion" in text_sec1.lower() or "sandbox" in text_sec1.lower()
    assert "message" in action_sec1

    res_sec2 = evaluate_pc_task("open powershell and install software")
    assert res_sec2 is not None
    text_sec2, action_sec2 = res_sec2
    assert action_sec2["type"] == "SECURITY_NOTICE"

    # 6. General Conversational Query (returns None for task so AI handles naturally)
    gen = evaluate_pc_task("who was alan turing")
    assert gen is None


@pytest.mark.asyncio
async def test_voice_status_endpoint(client):
    """Verify voice system operational status and male voice configuration."""
    user = await get_test_auth_user()
    resp = client.get("/api/voice/status", headers=user["auth_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "operational"
    assert "Ravi" in data.get("preferredMaleVoice", "") or "onyx" in data.get("preferredMaleVoice", "")
    assert data.get("wakePhrase") == "Hey NEXORA"
    assert data.get("speechRecognition") == "en-IN"


@pytest.mark.asyncio
async def test_wake_greet_endpoint(client):
    """Verify wake greet returns JARVIS-inspired greeting with male voice persona."""
    user = await get_test_auth_user()
    resp = client.post("/api/voice/wake-greet", json={"voice": "onyx"}, headers=user["auth_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "greeting" in data
    assert "listening" in data["greeting"].lower() or "nexora" in data["greeting"].lower()
    assert data.get("assistant") == "NEXORA"
    assert data.get("status") == "ready"


@pytest.mark.asyncio
async def test_voice_pipeline_direct_text_query(client):
    """Verify voice pipeline accepts direct spoken text and evaluates PC tasks."""
    user = await get_test_auth_user()
    # 1. Test time query
    req = {
        "text": "what time is it",
        "voice": "onyx",
        "model": "default"
    }
    resp = client.post("/api/voice/pipeline", json=req, headers=user["auth_headers"])
    assert resp.status_code == 200
    res = resp.json()
    assert res.get("text") is not None
    assert len(res["text"]) > 0
    assert res.get("action") is not None
    assert res["action"]["type"] == "TIME_CHECK"

    # 2. Test permitted site query
    req_site = {
        "text": "open github repository",
        "voice": "onyx",
        "model": "default"
    }
    resp_site = client.post("/api/voice/pipeline", json=req_site, headers=user["auth_headers"])
    assert resp_site.status_code == 200
    res_site = resp_site.json()
    assert res_site.get("action") is not None
    assert res_site["action"]["type"] == "OPEN_URL"
    assert "github.com" in res_site["action"]["url"]


@pytest.mark.asyncio
async def test_voice_synthesize_endpoint(client):
    """Verify voice synthesis with male voice onyx persona and custom pitch/speed."""
    user = await get_test_auth_user()
    req = {
        "text": "Greetings sir. NEXORA systems are operating at peak efficiency.",
        "voice": "onyx",
        "speed": 1.0,
        "pitch": 0.95
    }
    resp = client.post("/api/voice/synthesize", json=req, headers=user["auth_headers"])
    assert resp.status_code == 200
    res = resp.json()
    assert res.get("audioUrl") is not None or res.get("audioBase64") is not None
    assert res.get("voice") == "onyx"
    assert res.get("durationSeconds", 0) > 0



def test_voice_pipeline_unauthenticated_rejection(client):
    """Verify voice endpoints require authentication."""
    resp = client.post("/api/voice/pipeline", json={"text": "Hello"})
    assert resp.status_code in [401, 403]

    resp_synth = client.post("/api/voice/synthesize", json={"text": "Hello"})
    assert resp_synth.status_code in [401, 403]


@pytest.mark.asyncio
async def test_voice_error_handling_empty_payload(client):
    """Verify graceful error response when no text or audio is supplied."""
    user = await get_test_auth_user()
    resp = client.post(
        "/api/voice/pipeline",
        json={},
        headers=user["auth_headers"]
    )
    # Pipeline requires either audioBase64 or text
    assert resp.status_code == 400
    assert "audioBase64 or text" in resp.json()["detail"]


def test_zero_secrets_leakage_in_voice_responses(client):
    """Verify that internal keys, paths, and server secrets are never leaked."""
    resp = client.get("/api/voice/status")
    text_content = resp.text.lower()

    assert "jwt_secret_key" not in text_content
    assert "database_url" not in text_content
    assert "openai_api_key" not in text_content
    assert "render_api_key" not in text_content
