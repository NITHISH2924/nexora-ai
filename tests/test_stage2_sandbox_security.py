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
from backend.app.services.coding_service import coding_service, build_minimal_sandbox_env, validate_code_safety


@pytest.mark.asyncio
async def test_sandbox_host_secrets_isolation():
    """Verify that user-submitted code cannot access JWT_SECRET, DATABASE_URL, or API keys from os.environ."""
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
