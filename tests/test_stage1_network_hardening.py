"""
Stage 1: Enterprise Network & Transport Hardening Verification Suite
====================================================================
Tests:
1. CORS Strict Allowlist:
   - Untrusted cross-origin requests do not receive Access-Control-Allow-Origin.
   - Legitimate origins (localhost, frontend URL) receive proper CORS headers with credentials.
2. Comprehensive Security Headers:
   - Content-Security-Policy (CSP) with frame-ancestors 'none' and required asset allowlists.
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - Referrer-Policy: strict-origin-when-cross-origin
   - Cross-Origin-Opener-Policy: same-origin
   - Permissions-Policy
3. HSTS Enforcement:
   - Absent on standard local HTTP.
   - Present when request is verified HTTPS in production.
4. Spoof-Proof Client IP & Trusted Proxy Handling:
   - Direct connection ignores attacker-forged X-Forwarded-For.
   - Trusted proxy hop (Render / 127.0.0.1 / 10.x) safely extracts verified client IP.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.security import get_client_ip, is_trusted_proxy

client = TestClient(app, base_url="http://127.0.0.1:8000")


def test_cors_rejects_untrusted_origins():
    """Verify that random external origins are NOT granted CORS access."""
    untrusted_origins = [
        "https://evil-attacker.com",
        "http://attacker.org",
        "https://phishing-nexora.net",
        "http://198.51.100.5:9999"
    ]
    for origin in untrusted_origins:
        # Preflight OPTIONS request
        res = client.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        allow_origin = res.headers.get("access-control-allow-origin")
        assert allow_origin != origin, f"Vulnerability: Untrusted origin {origin} was allowed by CORS!"


def test_cors_allows_trusted_origins_with_credentials():
    """Verify that legitimate frontend origins receive CORS credentials support."""
    trusted = "http://localhost:8000"
    res = client.options(
        "/api/auth/login",
        headers={
            "Origin": trusted,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
    )
    assert res.headers.get("access-control-allow-origin") == trusted
    assert res.headers.get("access-control-allow-credentials") == "true"


def test_security_headers_present_on_pages_and_api():
    """Verify that defensive security headers are injected on all routes."""
    res = client.get("/")
    assert res.status_code == 200

    # Content-Security-Policy
    csp = res.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in csp
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "https://cdnjs.cloudflare.com" in csp

    # Framing and MIME protection
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert res.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert "microphone=(self)" in res.headers.get("Permissions-Policy", "")


def test_hsts_only_on_verified_https_in_production():
    """Verify HSTS is NOT sent over plain HTTP and only sent when HTTPS is verified in production."""
    # 1. Plain HTTP request in development/default
    res_http = client.get("/")
    assert "Strict-Transport-Security" not in res_http.headers

    # 2. Simulated HTTPS production request
    orig_env = settings.APP_ENV
    try:
        settings.APP_ENV = "production"
        res_https = client.get("/", headers={"x-forwarded-proto": "https"})
        assert "Strict-Transport-Security" in res_https.headers
        assert "max-age=31536000" in res_https.headers["Strict-Transport-Security"]
    finally:
        settings.APP_ENV = orig_env


def test_trusted_proxy_ip_resolution_resists_spoofing():
    """Verify client IP extraction defends against X-Forwarded-For header spoofing."""
    # Scenario A: Direct connection from untrusted public IP attempting to spoof X-Forwarded-For
    req_direct = MagicMock()
    req_direct.client.host = "198.51.100.22"
    req_direct.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}
    resolved = get_client_ip(req_direct)
    # Must return the direct peer IP, not the spoofed header
    assert resolved == "198.51.100.22"

    # Scenario B: Request through Render reverse proxy (127.0.0.1 or 10.x.x.x private IP)
    req_proxy = MagicMock()
    req_proxy.client.host = "127.0.0.1"
    req_proxy.headers = {"X-Forwarded-For": "203.0.113.99, 10.0.4.15"}
    resolved = get_client_ip(req_proxy)
    # Must skip the internal 10.x proxy and extract the real client 203.0.113.99
    assert resolved == "203.0.113.99"

    # Scenario C: Attacker sent a fake IP before hitting reverse proxy
    req_proxy_spoof = MagicMock()
    req_proxy_spoof.client.host = "10.0.0.2"
    req_proxy_spoof.headers = {"X-Forwarded-For": "1.1.1.1, 203.0.113.55"}
    resolved = get_client_ip(req_proxy_spoof)
    # The rightmost non-proxy IP added by the reverse proxy is 203.0.113.55
    assert resolved == "203.0.113.55"


def test_is_trusted_proxy_helper():
    """Verify trusted proxy network checker identifies loopback and private ranges."""
    assert is_trusted_proxy("127.0.0.1") is True
    assert is_trusted_proxy("10.0.1.5") is True
    assert is_trusted_proxy("172.16.0.1") is True
    assert is_trusted_proxy("192.168.1.1") is True
    assert is_trusted_proxy("203.0.113.50") is False
    assert is_trusted_proxy("8.8.8.8") is False
    assert is_trusted_proxy("malicious-string") is False
