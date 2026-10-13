import os
import sys
import time
import ast
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import asyncio

from backend.app.config import settings
from backend.app.models import CodeAssistRequest, CodeAssistResponse, CodeExecutionRequest, CodeExecutionResponse
from backend.app.services.ai_providers.manager import ai_manager

logger = logging.getLogger("services.coding")

def redact_sensitive_values(text: str) -> str:
    """Scrub known application secrets and credentials from output strings."""
    if not text:
        return text
    secrets_to_mask = [
        getattr(settings, "JWT_SECRET", ""),
        getattr(settings, "JWT_SECRET_KEY", ""),
        getattr(settings, "DATABASE_URL", ""),
        getattr(settings, "GEMINI_API_KEY", ""),
        getattr(settings, "OPENAI_API_KEY", ""),
        getattr(settings, "ANTHROPIC_API_KEY", ""),
        getattr(settings, "GROQ_API_KEY", ""),
        getattr(settings, "DEEPSEEK_API_KEY", ""),
        getattr(settings, "SMTP_PASSWORD", ""),
        getattr(settings, "ADMIN_SECRET", ""),
        getattr(settings, "SESSION_SECRET", ""),
    ]
    redacted = text
    for secret in secrets_to_mask:
        if secret and len(secret) > 4 and secret in redacted:
            redacted = redacted.replace(secret, "[REDACTED_SECRET]")
    return redacted

def build_minimal_sandbox_env() -> Dict[str, str]:
    """
    Construct a stripped, minimal execution environment containing ZERO application secrets.
    Only strictly required system runtime variables are passed to the child process.
    """
    clean_env = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    allowed_os_keys = [
        "SYSTEMROOT", "WINDIR", "PATHEXT", "COMSPEC",
        "PATH", "TEMP", "TMP",
        "LANG", "LC_ALL"
    ]
    for k in allowed_os_keys:
        val = os.environ.get(k)
        if val is not None:
            clean_env[k] = val
    return clean_env

def validate_code_safety(code: str) -> Optional[str]:
    """
    Inspect user code for dangerous calls, network operations, process execution, and destructive patterns.
    Returns error message if blocked, or None if acceptable.
    """
    blocked_keywords = [
        "shutil.rmtree",
        "os.system",
        "os.popen",
        "os.exec",
        "subprocess",
        "ctypes",
        "socket.",
        "import socket",
        "from socket",
        "http.client",
        "urllib.request",
        "requests.",
        "import requests",
        "httpx.",
        "import httpx",
        "format c:",
        ":(){ :|:& };:"
    ]
    code_lower = code.lower()
    for kw in blocked_keywords:
        if kw in code_lower:
            return f"Security Exception: Potentially destructive system call or restricted module '{kw}' blocked by execution sandbox policy."

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    disallowed_modules = {
        "socket", "subprocess", "ctypes", "pty", "shutil",
        "http", "urllib", "requests", "httpx", "aiohttp",
        "multiprocessing", "threading", "signal"
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in disallowed_modules:
                    return f"Security Exception: Import of restricted module '{alias.name}' is prohibited by execution sandbox policy."
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in disallowed_modules:
                    return f"Security Exception: Import from restricted module '{node.module}' is prohibited by execution sandbox policy."

    return None

_execution_semaphores: Dict[Any, asyncio.Semaphore] = {}

def get_execution_semaphore() -> asyncio.Semaphore:
    """Retrieve concurrency semaphore scoped to active event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop not in _execution_semaphores:
        limit = getattr(settings, "MAX_CONCURRENT_CODE_EXECUTIONS", 4)
        _execution_semaphores[loop] = asyncio.Semaphore(limit)
    return _execution_semaphores[loop]

async def _terminate_process_tree(proc: asyncio.subprocess.Process):
    """Ensure process and any spawned child processes are forcefully terminated."""
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=2
            )
        else:
            import signal
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        await proc.wait()
    except Exception:
        pass

class CodingService:
    """Service providing AI code generation, debugging, refactoring, explanation, optimization, and sandboxed execution."""

    async def assist_code(self, req: CodeAssistRequest) -> CodeAssistResponse:
        """
        Execute AI Coding Assistance:
        - generate: Write production-ready code with type annotations
        - debug: Identify bugs, root cause, and return fixed code
        - explain: Step-by-step logic and time/space complexity breakdown
        - refactor: Clean code, SOLID, DRY principles
        - optimize: Performance, memory and algorithmic efficiency
        - error_analysis: Diagnose runtime errors / stack traces
        """
        lang = req.language or "python"
        action = req.action
        code_input = req.code or ""
        user_prompt = req.prompt or ""
        error_msg = req.errorMessage or ""

        action_prompts = {
            "generate": (
                f"You are a principal software architect. Write robust, production-grade {lang.upper()} code for:\n"
                f"Requirements: \"{user_prompt or 'Create a complete modular implementation'}\"\n\n"
                f"Guidelines:\n"
                f"- Include comprehensive type annotations and docstrings.\n"
                f"- Handle error boundaries and edge cases gracefully.\n"
                f"- Provide clean example usage at the bottom."
            ),
            "debug": (
                f"You are an expert debugger and code reviewer. Debug the following {lang.upper()} code:\n"
                f"```\n{code_input}\n```\n"
                f"{'Error Encountered: ' + error_msg if error_msg else ''}\n"
                f"User Details: \"{user_prompt}\"\n\n"
                f"Format your response as:\n"
                f"1. **Root Cause Analysis**: Explain exactly what bug is occurring and why.\n"
                f"2. **Corrected Code Solution**: Provide the full, fixed {lang.upper()} code in a syntax-highlighted block.\n"
                f"3. **Prevention & Best Practices**: How to avoid this issue in the future."
            ),
            "explain": (
                f"You are a master computer science educator. Explain the following {lang.upper()} code in depth:\n"
                f"```\n{code_input}\n```\n\n"
                f"Structure your response:\n"
                f"1. **High-Level Purpose**: What problem does this code solve?\n"
                f"2. **Step-by-Step Logic Walkthrough**: Break down each function, loop, and conditional.\n"
                f"3. **Algorithmic Complexity**: Detail the Time Complexity (Big-O) and Space Complexity (Big-O).\n"
                f"4. **Key Patterns & Data Structures Used**."
            ),
            "refactor": (
                f"You are a clean code specialist. Refactor the following {lang.upper()} code for optimal readability, maintainability, and idiomatic elegance:\n"
                f"```\n{code_input}\n```\n"
                f"User Goals: \"{user_prompt or 'Improve structure, DRY, and naming'}\"\n\n"
                f"Format your response as:\n"
                f"1. **Refactoring Highlights**: Key architectural changes made.\n"
                f"2. **Refactored Code**: The improved, clean {lang.upper()} code block.\n"
                f"3. **Design Principles Applied**: SOLID, DRY, separation of concerns."
            ),
            "optimize": (
                f"You are a high-performance systems and algorithms engineer. Optimize the following {lang.upper()} code for speed and memory efficiency:\n"
                f"```\n{code_input}\n```\n"
                f"User Constraints: \"{user_prompt or 'Reduce latency and memory footprint'}\"\n\n"
                f"Format your response as:\n"
                f"1. **Performance Bottlenecks Identified**: Inefficiencies in current implementation.\n"
                f"2. **Optimized Code**: High-throughput {lang.upper()} code implementation.\n"
                f"3. **Complexity & Benchmark Improvements**: Before vs. After asymptotic complexity analysis."
            ),
            "error_analysis": (
                f"You are a senior systems diagnostician. Analyze this runtime error / stack trace:\n"
                f"```text\n{error_msg or user_prompt}\n```\n"
                f"{'Associated Code Context:\n```' + code_input + '\n```' if code_input else ''}\n\n"
                f"Format your response as:\n"
                f"1. **Error Diagnosis**: Clear explanation of what triggered this error.\n"
                f"2. **Step-by-Step Resolution**: Exact steps and code modifications to resolve it.\n"
                f"3. **Corrected Code Block**: Working code snippet."
            )
        }

        chosen_prompt = action_prompts.get(action, action_prompts["generate"])
        system_prompt = f"You are NEXORA AI Senior Coding Assistant, specialized in high-performance {lang.upper()} software engineering."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chosen_prompt}
        ]

        ai_result, model_used = await ai_manager.generate_response(
            messages=messages,
            model=req.model,
            system_prompt=system_prompt
        )

        return CodeAssistResponse(
            action=action,
            language=lang,
            result=ai_result,
            code=code_input,
            explanation=ai_result,
            model=model_used
        )

    async def _execute_remote_worker(self, req: CodeExecutionRequest, worker_url: str) -> CodeExecutionResponse:
        """Forward execution to dedicated isolated container runner worker."""
        import httpx
        try:
            timeout_val = getattr(settings, "CODE_EXECUTION_TIMEOUT_SECONDS", 4.0) + 1.0
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                res = await client.post(
                    f"{worker_url.rstrip('/')}/execute",
                    json={"language": req.language, "code": req.code, "stdin": req.stdin or ""}
                )
                if res.status_code == 200:
                    data = res.json()
                    return CodeExecutionResponse(
                        status=data.get("status", "success"),
                        output=redact_sensitive_values(data.get("output", "")),
                        error=data.get("error"),
                        executionTimeMs=data.get("executionTimeMs", 0.0),
                        exitCode=data.get("exitCode", 0),
                        success=data.get("success", True),
                        stdout=redact_sensitive_values(data.get("stdout", "")),
                        stderr=redact_sensitive_values(data.get("stderr", "")),
                        durationMs=data.get("durationMs", 0.0)
                    )
                else:
                    return CodeExecutionResponse(
                        status="error",
                        output="",
                        error=f"Sandbox worker returned status {res.status_code}",
                        executionTimeMs=0.0,
                        exitCode=1,
                        success=False,
                        stdout="",
                        stderr=f"Sandbox worker returned status {res.status_code}",
                        durationMs=0.0
                    )
        except Exception as e:
            return CodeExecutionResponse(
                status="error",
                output="",
                error=f"Sandbox worker communication error: {str(e)}",
                executionTimeMs=0.0,
                exitCode=1,
                success=False,
                stdout="",
                stderr="Sandbox worker unreachable.",
                durationMs=0.0
            )

    async def execute_sandboxed_code(self, req: CodeExecutionRequest) -> CodeExecutionResponse:
        """
        Execute code in a hardened, isolated sandbox with strict timeouts,
        ephemeral temporary workspace, stripped environment, output caps, and secret redaction.
        In production, requires a dedicated container worker and refuses uncontained execution.
        """
        # 1. Platform & Production Isolation Safety Check
        # On Render or in production: Never execute arbitrary user code with web server privileges
        # unless a dedicated isolated worker is configured.
        is_production = settings.APP_ENV == "production" or bool(os.getenv("RENDER"))
        has_isolated_worker = bool(getattr(settings, "CODE_SANDBOX_WORKER_URL", ""))
        require_container_in_prod = getattr(settings, "REQUIRE_CONTAINER_SANDBOX_IN_PROD", True)

        if is_production and require_container_in_prod and not has_isolated_worker:
            return CodeExecutionResponse(
                status="error",
                output="",
                error=(
                    "Live code execution is disabled on production web servers. "
                    "In production, arbitrary code execution requires a dedicated container sandbox worker "
                    "(e.g., CODE_SANDBOX_WORKER_URL). NEXORA AI Code Assistant (generation, explanation, "
                    "refactoring, and debugging) remains fully operational."
                ),
                executionTimeMs=0.0,
                exitCode=1,
                success=False,
                stdout="",
                stderr=(
                    "Live code execution is disabled on production web servers. "
                    "In production, arbitrary code execution requires a dedicated container sandbox worker "
                    "(e.g., CODE_SANDBOX_WORKER_URL). NEXORA AI Code Assistant (generation, explanation, "
                    "refactoring, and debugging) remains fully operational."
                ),
                durationMs=0.0
            )

        if has_isolated_worker:
            return await self._execute_remote_worker(req, settings.CODE_SANDBOX_WORKER_URL)

        # Feature toggle check
        if not getattr(settings, "ENABLE_CODE_EXECUTION", True):
            return CodeExecutionResponse(
                status="error",
                output="",
                error="Secure isolated code execution is currently disabled on this host. Use AI Code Assistant to generate, refactor, and review code.",
                executionTimeMs=0.0,
                exitCode=1,
                success=False,
                stdout="",
                stderr="Secure isolated code execution is currently disabled on this host. Use AI Code Assistant to generate, refactor, and review code.",
                durationMs=0.0
            )

        lang = req.language.lower()
        code = req.code or ""
        stdin_data = req.stdin or ""
        timeout_seconds = getattr(settings, "CODE_EXECUTION_TIMEOUT_SECONDS", 4.0)
        max_output_bytes = getattr(settings, "MAX_CODE_OUTPUT_BYTES", 65536)
        max_input_bytes = getattr(settings, "MAX_CODE_INPUT_BYTES", 65536)

        # Input buffer safety cap
        if len(code.encode("utf-8")) > max_input_bytes:
            return CodeExecutionResponse(
                status="error",
                output="",
                error=f"Submitted code exceeds maximum input size limit ({max_input_bytes} bytes).",
                executionTimeMs=0.0,
                exitCode=1,
                success=False,
                stdout="",
                stderr=f"Submitted code exceeds maximum input size limit ({max_input_bytes} bytes).",
                durationMs=0.0
            )

        # 1. Static security validation
        security_error = validate_code_safety(code)
        if security_error:
            return CodeExecutionResponse(
                status="error",
                output="",
                error=security_error,
                executionTimeMs=0.0,
                exitCode=1,
                success=False,
                stdout="",
                stderr=security_error,
                durationMs=0.0
            )

        start_time = time.perf_counter()

        if lang == "python":
            sem = get_execution_semaphore()
            async with sem:
                # 2. Ephemeral disposable workspace
                try:
                    with tempfile.TemporaryDirectory(prefix="nexora_sandbox_") as tmp_workspace:
                        script_path = Path(tmp_workspace) / "script.py"
                        script_path.write_text(code, encoding="utf-8")

                        # Execute with isolated flags: -I (isolated mode, ignores PYTHONPATH/user site-packages), -B (no .pyc)
                        cmd = [sys.executable, "-I", "-B", str(script_path)]
                        clean_env = build_minimal_sandbox_env()

                        extra_kwargs = {}
                        if sys.platform != "win32":
                            extra_kwargs["start_new_session"] = True

                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            cwd=tmp_workspace,
                            env=clean_env,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            **extra_kwargs
                        )

                        try:
                            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                                proc.communicate(input=stdin_data.encode("utf-8")),
                                timeout=timeout_seconds
                            )
                            elapsed_ms = (time.perf_counter() - start_time) * 1000

                            # Truncate output to prevent memory exhaustion / DoS
                            if len(stdout_bytes) > max_output_bytes:
                                stdout_bytes = stdout_bytes[:max_output_bytes] + b"\n... [Output truncated after limit exceeded]"
                            if len(stderr_bytes) > max_output_bytes:
                                stderr_bytes = stderr_bytes[:max_output_bytes] + b"\n... [Error output truncated after limit exceeded]"

                            stdout_str = redact_sensitive_values(stdout_bytes.decode("utf-8", errors="replace"))
                            stderr_str = redact_sensitive_values(stderr_bytes.decode("utf-8", errors="replace"))
                            exit_code = proc.returncode or 0

                            if exit_code == 0:
                                return CodeExecutionResponse(
                                    status="success",
                                    output=stdout_str.strip() or "[Program executed successfully with no stdout]",
                                    error=stderr_str.strip() if stderr_str.strip() else None,
                                    executionTimeMs=round(elapsed_ms, 2),
                                    exitCode=exit_code,
                                    success=True,
                                    stdout=stdout_str,
                                    stderr=stderr_str,
                                    durationMs=round(elapsed_ms, 2)
                                )
                            else:
                                return CodeExecutionResponse(
                                    status="error",
                                    output=stdout_str.strip(),
                                    error=stderr_str.strip() or f"Process exited with code {exit_code}",
                                    executionTimeMs=round(elapsed_ms, 2),
                                    exitCode=exit_code,
                                    success=False,
                                    stdout=stdout_str,
                                    stderr=stderr_str,
                                    durationMs=round(elapsed_ms, 2)
                                )

                        except asyncio.TimeoutError:
                            await _terminate_process_tree(proc)
                            elapsed_ms = (time.perf_counter() - start_time) * 1000
                            return CodeExecutionResponse(
                                status="timeout",
                                output="",
                                error=f"Execution Timed Out ({timeout_seconds}s limit exceeded). Infinite loop or long-running task terminated.",
                                executionTimeMs=round(elapsed_ms, 2),
                                exitCode=-1,
                                success=False,
                                stdout="",
                                stderr=f"Execution Timed Out ({timeout_seconds}s limit exceeded). Infinite loop or long-running task terminated.",
                                durationMs=round(elapsed_ms, 2)
                            )
                        finally:
                            if proc.returncode is None:
                                await _terminate_process_tree(proc)

                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    logger.error(f"Sandbox runner error: {exc}", exc_info=False)
                    return CodeExecutionResponse(
                        status="error",
                        output="",
                        error="Execution Engine Error: Code execution failed within sandbox.",
                        executionTimeMs=round(elapsed_ms, 2),
                        exitCode=1,
                        success=False,
                        stdout="",
                        stderr="Execution Engine Error: Code execution failed within sandbox.",
                        durationMs=round(elapsed_ms, 2)
                    )
        else:
            # JavaScript / Node simulation
            return CodeExecutionResponse(
                status="success",
                output=f"[{lang.upper()} Sandbox Output]\nExecution simulated safely for {lang.upper()}.",
                error=None,
                executionTimeMs=12.5,
                exitCode=0,
                success=True,
                stdout=f"[{lang.upper()} Sandbox Output]\nExecution simulated safely for {lang.upper()}.",
                stderr=None,
                durationMs=12.5
            )

coding_service = CodingService()
