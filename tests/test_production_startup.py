import os
import pytest
from starlette.testclient import TestClient
from backend.app.main import app, lifespan
from backend.app.database import get_db, create_tables, is_postgres
from backend.app.config import settings

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoints(client):
    """Verify that public health-check endpoints return 200 OK without requiring authentication."""
    for path in ["/api/health", "/health"]:
        res = client.get(path)
        assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"
        data = res.json()
        assert data.get("status") == "healthy"
        assert "app" in data
        assert "environment" in data

def test_signup_and_login_routes(client):
    """Verify clean URL page routes return 200 OK HTML."""
    res_signup = client.get("/signup")
    assert res_signup.status_code == 200
    assert "Create Account" in res_signup.text
    assert "signup-form" in res_signup.text

    res_login = client.get("/login")
    assert res_login.status_code == 200
    assert "Sign In" in res_login.text

    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "NEXORA AI" in res_root.text

@pytest.mark.asyncio
async def test_lifespan_startup_resilience():
    """Verify that FastAPI lifespan startup completes successfully."""
    async with lifespan(app):
        # Lifespan must complete startup without raising exceptions
        assert True

@pytest.mark.asyncio
async def test_database_graceful_fallback(monkeypatch):
    """
    Simulate an unreachable PostgreSQL DATABASE_URL.
    Verify get_db() gracefully falls back to local SQLite and does NOT crash.
    """
    # Point to an unreachable host with immediate fail
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://invalid_user:invalid_pass@127.0.0.1:54329/invalid_db")
    
    # get_db should not raise, but instead yield SQLite fallback connection
    async with get_db() as db:
        assert db is not None
        # Verify basic query works on the fallback DB
        cursor = await db.execute("SELECT 1 AS alive")
        row = await cursor.fetchone()
        assert row is not None
        assert row["alive"] == 1
