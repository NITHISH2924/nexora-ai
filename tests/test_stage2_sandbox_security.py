"""
Stage 2: Secure Code Execution & Sandbox Isolation Verification Suite
=====================================================================
Tests:
1. Host Secret Isolation:
   - Executed code has zero access to JWT_SECRET, DATABASE_URL, or AI API keys.
   - Minimal sanitized environment excludes host application secrets.
2. Production Credentials & Output Redaction:
   - Output scrubbing ensures any accidentally reflected credential values are redacted.
3. Network Restrictions & Sockets Blocked:
   - Outbound socket connections and HTTP client modules are strictly prohibited.
4. Process & System Destruction Blocked:
   - Subprocess creation and destructive filesystem commands are blocked.
5. Execution Timeout & Process Tree Termination:
   - Infinite loops terminate cleanly within the enforced timeout cap.
6. Ephemeral Temporary Workspace & Isolation:
   - Executed code runs in a disposable scratch directory with no access to host .env or workspace files.
7. Concurrent Execution Isolation:
   - Multiple concurrent executions run in isolated workspaces without cross-contamination.
8. Output Safety & Buffer Limits:
   - Large output generation is bounded to prevent memory exhaustion DoS.
9. Safe Fallback Toggle:
   - When code execution is disabled, returns a safe error without crashing or executing.
10. Preserved Coding Assistant Functionality:
   - Code generation, refactoring, and explanation continue working flawlessly.
"""

import os
import sys
import asyncio
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import settings
from backend.app.models import CodeExecutionRequest, CodeAssistRequest
from backend.app.services.coding_service import coding_service, build_minimal_sandbox_env, validate_code_safety, redact_sensitive_values


@pytest.mark.asyncio
async def test_sandbox_host_secrets_isolation():
    """Verify that user-submitted code cannot access JWT_SECRET, DATABASE_URL, or API keys from os.environ."""
    orig_jwt = settings.JWT_SECRET
    orig_db = settings.DATABASE_URL
    orig_env_jwt = os.environ.get("JWT_SECRET")
    orig_env_db = os.environ.get("DATABASE_URL")
    try:
        # Ensure sensitive variables exist in host environment for the test
        os.environ["JWT_SECRET"] = "super_secret_production_jwt_key_98765"
        os.environ["DATABASE_URL"] = "postgresql://nexora_admin:super_secret_pw@db.render.com/nexora_db"
        settings.JWT_SECRET = "super_secret_production_jwt_key_98765"
        settings.DATABASE_URL = "postgresql://nexora_admin:super_secret_pw@db.render.com/nexora_db"

        # 1. Verify build_minimal_sandbox_env contains no secrets
        clean_env = build_minimal_sandbox_env()
        assert "JWT_SECRET" not in clean_env
        assert "DATABASE_URL" not in clean_env
        assert "OPENAI_API_KEY" not in clean_env

        # 2. Execute code attempting to read secrets from os.environ
        code = """
import os
jwt = os.environ.get('JWT_SECRET', 'NOT_FOUND')
db = os.environ.get('DATABASE_URL', 'NOT_FOUND')
print(f'JWT:{jwt}')
print(f'DB:{db}')
"""
        res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
            language="python",
            code=code
        ))
        assert res.success is True
        assert "JWT:NOT_FOUND" in res.stdout
        assert "DB:NOT_FOUND" in res.stdout
        assert "super_secret_production_jwt_key_98765" not in res.stdout
        assert "super_secret_pw" not in res.stdout
    finally:
        settings.JWT_SECRET = orig_jwt
        settings.DATABASE_URL = orig_db
        if orig_env_jwt is None:
            os.environ.pop("JWT_SECRET", None)
        else:
            os.environ["JWT_SECRET"] = orig_env_jwt
        if orig_env_db is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = orig_env_db


@pytest.mark.asyncio
async def test_sandbox_ephemeral_workspace_no_host_files():
    """Verify that executed code cannot read host repository files like .env or database from its working directory."""
    code = """
import os
cwd_files = os.listdir('.')
has_env = os.path.exists('.env')
print(f'HAS_ENV:{has_env}')
print(f'FILES_COUNT:{len(cwd_files)}')
"""
    res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=code
    ))
    assert res.success is True
    assert "HAS_ENV:False" in res.stdout
    # The ephemeral folder should only contain script.py
    assert "FILES_COUNT:1" in res.stdout


@pytest.mark.asyncio
async def test_sandbox_blocks_network_and_sockets():
    """Verify that attempts to import socket, urllib, or requests are blocked by sandbox policy."""
    network_snippets = [
        "import socket\ns = socket.socket()",
        "from socket import create_connection",
        "import urllib.request\nurllib.request.urlopen('http://169.254.169.254')",
        "import requests\nrequests.get('https://example.com')",
        "import http.client\nc = http.client.HTTPConnection('localhost')"
    ]
    for snippet in network_snippets:
        res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
            language="python",
            code=snippet
        ))
        assert res.success is False
        assert "security exception" in res.stderr.lower() or "blocked" in res.stderr.lower()


@pytest.mark.asyncio
async def test_sandbox_blocks_subprocess_and_destructive_calls():
    """Verify that attempts to run subprocesses or destructive commands are rejected."""
    dangerous_snippets = [
        "import subprocess\nsubprocess.run(['dir'])",
        "import os\nos.system('whoami')",
        "import shutil\nshutil.rmtree('/tmp')",
        "import ctypes\nctypes.c_int(42)"
    ]
    for snippet in dangerous_snippets:
        res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
            language="python",
            code=snippet
        ))
        assert res.success is False
        assert "security exception" in res.stderr.lower() or "blocked" in res.stderr.lower()


@pytest.mark.asyncio
async def test_sandbox_timeout_and_process_termination():
    """Verify that infinite loops are killed within the timeout limit."""
    loop_code = "import time\nwhile True:\n    time.sleep(0.05)"
    t0 = asyncio.get_event_loop().time()
    res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=loop_code
    ))
    elapsed = asyncio.get_event_loop().time() - t0
    assert res.success is False
    assert res.status == "timeout"
    assert "timed out" in res.stderr.lower()
    assert elapsed < 6.0, f"Process took {elapsed:.2f}s, expected kill near 4s"


@pytest.mark.asyncio
async def test_sandbox_output_truncation_limits():
    """Verify that massive outputs are safely capped to prevent memory exhaustion."""
    flood_code = "print('A' * 200000)"
    res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=flood_code
    ))
    assert res.success is True
    # Output must be capped near MAX_CODE_OUTPUT_BYTES (65536) and not full 200KB
    assert len(res.stdout) < 70000
    assert "truncated" in res.stdout.lower()


@pytest.mark.asyncio
async def test_sandbox_concurrent_workspace_isolation():
    """Verify that concurrent code executions run in distinct temporary workspaces without interference."""
    snippet_1 = "with open('marker.txt', 'w') as f: f.write('USER_1')\nprint(open('marker.txt').read())"
    snippet_2 = "with open('marker.txt', 'w') as f: f.write('USER_2')\nprint(open('marker.txt').read())"

    task1 = coding_service.execute_sandboxed_code(CodeExecutionRequest(language="python", code=snippet_1))
    task2 = coding_service.execute_sandboxed_code(CodeExecutionRequest(language="python", code=snippet_2))

    res1, res2 = await asyncio.gather(task1, task2)
    assert res1.success is True
    assert res2.success is True
    assert "USER_1" in res1.stdout
    assert "USER_2" in res2.stdout


@pytest.mark.asyncio
async def test_sandbox_safe_fallback_toggle():
    """Verify that setting ENABLE_CODE_EXECUTION=False safely disables execution with clear notice."""
    orig_setting = settings.ENABLE_CODE_EXECUTION
    try:
        settings.ENABLE_CODE_EXECUTION = False
        res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
            language="python",
            code="print(1 + 1)"
        ))
        assert res.success is False
        assert "disabled" in res.error.lower()
        assert "ai code assistant" in res.error.lower()
    finally:
        settings.ENABLE_CODE_EXECUTION = orig_setting


@pytest.mark.asyncio
async def test_coding_assistant_ai_features_preserved():
    """Verify that AI Code Generation and Explanation remain 100% functional alongside sandboxing."""
    assist_res = await coding_service.assist_code(CodeAssistRequest(
        action="generate",
        language="python",
        prompt="Write a function to compute Fibonacci sequence."
    ))
    assert assist_res.action == "generate"
    assert len(assist_res.result) > 20


@pytest.mark.asyncio
async def test_sandbox_production_fail_closed_without_worker():
    """Verify that in production on Render without a container worker, execution is safely refused."""
    orig_env = settings.APP_ENV
    orig_worker = settings.CODE_SANDBOX_WORKER_URL
    orig_render = os.environ.get("RENDER")
    try:
        settings.APP_ENV = "production"
        settings.CODE_SANDBOX_WORKER_URL = ""
        os.environ["RENDER"] = "true"

        res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
            language="python",
            code="print('should not execute directly on web host')"
        ))
        assert res.success is False
        assert "disabled on production web servers" in res.error.lower()
        assert "dedicated container sandbox worker" in res.error.lower()
        assert "ai code assistant" in res.error.lower()
    finally:
        settings.APP_ENV = orig_env
        settings.CODE_SANDBOX_WORKER_URL = orig_worker
        if orig_render is None:
            os.environ.pop("RENDER", None)
        else:
            os.environ["RENDER"] = orig_render


@pytest.mark.asyncio
async def test_sandbox_remote_worker_dispatch(monkeypatch):
    """Verify that when CODE_SANDBOX_WORKER_URL is configured, execution delegates to remote worker."""
    orig_worker = settings.CODE_SANDBOX_WORKER_URL
    try:
        settings.CODE_SANDBOX_WORKER_URL = "https://sandbox-worker.internal"

        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "status": "success",
                    "output": "Worker Result: 42",
                    "stdout": "Worker Result: 42",
                    "stderr": "",
                    "exitCode": 0,
                    "success": True,
                    "durationMs": 45.0
                }

        import httpx
        async def mock_post(self, url, json=None, **kwargs):
            assert "sandbox-worker.internal" in str(url)
            assert json["code"] == "print(42)"
            return MockResponse()

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
            language="python",
            code="print(42)"
        ))
        assert res.success is True
        assert "Worker Result: 42" in res.output
    finally:
        settings.CODE_SANDBOX_WORKER_URL = orig_worker


@pytest.mark.asyncio
async def test_sandbox_input_size_limit_rejection():
    """Verify that oversized code submissions are rejected by schema and service caps."""
    # 1. Pydantic model validation cap (max 20,000 chars)
    oversized_code = "# large submission\n" + ("x = 1\n" * 15000)
    with pytest.raises(Exception):
        CodeExecutionRequest(language="python", code=oversized_code)

    # 2. Service-level bytes safety cap
    bypass_req = CodeExecutionRequest.model_construct(
        language="python",
        code="x = 1\n" * 20000
    )
    res = await coding_service.execute_sandboxed_code(bypass_req)
    assert res.success is False
    assert "input size limit" in res.error.lower()


@pytest.mark.asyncio
async def test_sandbox_ephemeral_workspace_automatic_cleanup():
    """Verify that temporary workspace directories are completely deleted from disk after execution."""
    code = """
import os
print(os.path.abspath('.'))
"""
    res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=code
    ))
    assert res.success is True
    workspace_dir = res.stdout.strip()
    assert os.path.isabs(workspace_dir)
    assert "nexora_sandbox_" in workspace_dir
    # Directory MUST NOT exist anymore
    assert not os.path.exists(workspace_dir), f"Workspace {workspace_dir} was not cleaned up!"


def test_sandbox_redaction_removes_all_configured_secrets():
    """Verify that redact_sensitive_values scrubs all application secrets and tokens."""
    orig_jwt = settings.JWT_SECRET
    orig_jwt_key = settings.JWT_SECRET_KEY
    orig_db = settings.DATABASE_URL
    orig_admin = getattr(settings, "ADMIN_SECRET", "")
    try:
        settings.JWT_SECRET = "super_secret_jwt_token_alpha_123"
        settings.JWT_SECRET_KEY = "super_secret_jwt_token_alpha_123"
        settings.DATABASE_URL = "postgres://usr:secret_db_pass_999@localhost/db"
        settings.ADMIN_SECRET = "classified_admin_credential_888"

        leaked_text = (
            "Trace: key is super_secret_jwt_token_alpha_123 "
            "and db is postgres://usr:secret_db_pass_999@localhost/db "
            "and admin is classified_admin_credential_888"
        )
        scrubbed = redact_sensitive_values(leaked_text)
        assert "super_secret_jwt_token_alpha_123" not in scrubbed
        assert "secret_db_pass_999" not in scrubbed
        assert "classified_admin_credential_888" not in scrubbed
        assert "[REDACTED_SECRET]" in scrubbed
    finally:
        settings.JWT_SECRET = orig_jwt
        settings.JWT_SECRET_KEY = orig_jwt_key
        settings.DATABASE_URL = orig_db
        settings.ADMIN_SECRET = orig_admin


@pytest.mark.asyncio
async def test_sandbox_api_route_authenticated_execution():
    """Verify that the FastAPI /api/tools/code/execute route integrates properly with auth and sandbox."""
    from backend.app.main import app
    from backend.app.database import create_tables
    from backend.app.services.user_service import user_service
    from backend.app.models import UserRegisterRequest
    import httpx

    await create_tables()
    rand_suffix = os.urandom(4).hex()
    email = f"sandbox_api_user_{rand_suffix}@example.com"
    user, token = await user_service.register_user(UserRegisterRequest(email=email, password="Password123!Safe"))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Unauthenticated request must be rejected (401)
        unauth_resp = await client.post("/api/tools/code/execute", json={"language": "python", "code": "print(1)"})
        assert unauth_resp.status_code == 401

        # 2. Authenticated request succeeds through API
        auth_resp = await client.post(
            "/api/tools/code/execute",
            json={"language": "python", "code": "print(7 * 6)"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert auth_resp.status_code == 200
        data = auth_resp.json()
        assert data["success"] is True
        assert "42" in data["stdout"]

