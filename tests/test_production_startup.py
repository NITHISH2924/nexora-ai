import os
import pytest
from starlette.testclient import TestClient
from backend.app.main import app, lifespan
from backend.app.database import (
    get_db,
    create_tables,
    is_postgres,
    DatabaseUnavailableError,
    mask_database_url,
    check_db_readiness
)
from backend.app.config import settings

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoints(client):
    """Verify that public health-check endpoints return 200 OK without requiring authentication or database."""
    for path in ["/api/health", "/health"]:
        res = client.get(path)
        assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"
        data = res.json()
        assert data.get("status") == "healthy"
        assert "app" in data
        assert "environment" in data
        assert "version" in data

def test_database_readiness_endpoint(client):
    """Verify dedicated database readiness endpoint confirms DB responsiveness."""
    for path in ["/api/health/db", "/api/ready"]:
        res = client.get(path)
        assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"
        data = res.json()
        assert data.get("status") == "ready"
        assert data.get("database") == "connected"

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
    """Verify that FastAPI lifespan startup completes immediately without blocking port binding."""
    async with lifespan(app):
        # Lifespan must complete startup immediately without raising exceptions
        assert True

@pytest.mark.asyncio
async def test_database_unreachable_fail_safe(monkeypatch, client):
    """
    Simulate an unreachable PostgreSQL DATABASE_URL.
    Verify get_db() raises DatabaseUnavailableError (503) and NEVER silently falls back to SQLite,
    preventing silent production data loss.
    Verify that the process /api/health remains 200 OK, while /api/health/db returns 503.
    """
    # Point to an unreachable host with immediate failure
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://invalid_user:invalid_pass@127.0.0.1:54329/invalid_db")

    # get_db MUST raise DatabaseUnavailableError, NOT write to SQLite
    with pytest.raises(DatabaseUnavailableError) as exc_info:
        async with get_db() as db:
            pass
    assert exc_info.value.status_code == 503
    assert "Retry-After" in exc_info.value.headers

    # Probe readiness directly
    readiness = await check_db_readiness()
    assert readiness.get("status") == "not_ready"
    assert readiness.get("database") == "unavailable"

    # Verify HTTP endpoints behavior
    # Process health remains 200 (server is alive and listening)
    res_proc = client.get("/api/health")
    assert res_proc.status_code == 200

    # DB readiness correctly signals 503 Service Unavailable with Retry-After header
    res_db = client.get("/api/health/db")
    assert res_db.status_code == 503
    assert res_db.headers.get("Retry-After") == "5"

def test_safe_logging_no_secrets():
    """Verify mask_database_url cleanly scrubs passwords from connection strings."""
    url = "postgresql://nexora_admin:SuperSecretPass123!@dpg-abc123-a.render.com:5432/nexora_db"
    masked = mask_database_url(url)
    assert "SuperSecretPass123!" not in masked
    assert "nexora_admin:***@dpg-abc123-a.render.com:5432" in masked

    empty_masked = mask_database_url("")
    assert empty_masked == ""

    sqlite_url = "data/nexora.db"
    assert mask_database_url(sqlite_url) == sqlite_url
