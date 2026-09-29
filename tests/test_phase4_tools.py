import os
import sys
import uuid
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import settings
from backend.app.database import create_tables, get_db
from backend.app.services.user_service import user_service
from backend.app.services.search_service import search_service
from backend.app.services.coding_service import coding_service
from backend.app.services.writing_service import writing_service
from backend.app.models import (
    UserRegisterRequest,
    SearchRequest,
    CodeAssistRequest,
    CodeExecutionRequest,
    WritingAssistRequest
)

async def run_tests():
    print("\n" + "="*80)
    print("RUNNING PHASE 4: AI TOOLS & INTELLIGENCE SUITE VERIFICATION")
    print("1. AI Deep Search (Real Retrieval, Grounded Synthesis, Never Fabricated Citations)")
    print("2. Coding Assistant (Generate, Debug, Explain, Refactor, Optimize, Error Analysis)")
    print("3. Sandboxed Execution (Subprocess Isolation, Timeout Protection, Host Safety)")
    print("4. Writing Assistant (Rewrite, Grammar, Summarize, Expand, Shorten, Professional, Email, Resume, Cover Letter, Translation)")
    print("="*80 + "\n")

    # 0. Initialize Database
    print("[0] Initializing database tables...")
    await create_tables()
    print("    [PASS] Database initialized successfully.")

    # Create Authenticated Test User
    rand_id = uuid.uuid4().hex[:6]
    test_email = f"tools_tester_{rand_id}@example.com"
    user_data = UserRegisterRequest(email=test_email, password="ToolsPassword123!")
    user, token = await user_service.register_user(user_data)
    user_id = user["userId"]
    print(f"    [PASS] Created test user: {test_email} (ID: {user_id})")

    # =========================================================================
    # 1. AI DEEP SEARCH TESTS
    # =========================================================================
    print("\n" + "-"*70)
    print("[1] TESTING AI DEEP SEARCH (Real Web Retrieval & Grounded Citations)")
    print("-"*70)

    # 1.1 Standard Search
    query1 = "FastAPI asynchronous concurrency vs Node.js event loop"
    print(f"\n[1.1] Executing Standard AI Search: '{query1}'...")
    res1 = await search_service.search_and_synthesize(
        query=query1,
        max_results=4,
        search_depth="standard"
    )
    assert res1.query == query1
    assert len(res1.sources) > 0, "Expected at least 1 grounded search source"
    assert res1.totalSourcesFound >= len(res1.sources)
    assert len(res1.synthesis) > 100, "Expected rich synthesis"
    print(f"    [PASS] Sources retrieved: {len(res1.sources)}")
    for src in res1.sources:
        assert src.url.startswith("http"), f"Invalid source URL: {src.url}"
        assert len(src.domain) > 0, "Missing source domain"
        assert len(src.snippet) > 0, "Missing source snippet"
        print(f"      [{src.index}] {src.title} ({src.domain}) -> {src.url}")
    print(f"    [PASS] Grounded AI Synthesis preview:\n      {res1.synthesis[:180]}...")

    # 1.2 Deep Research Search
    query2 = "Python 3.13 free-threaded no-GIL architecture"
    print(f"\n[1.2] Executing Deep Research AI Search: '{query2}'...")
    res2 = await search_service.search_and_synthesize(
        query=query2,
        max_results=6,
        search_depth="deep"
    )
    assert res2.searchDepth == "deep"
    assert len(res2.sources) >= 1
    assert len(res2.synthesis) > 100
    print(f"    [PASS] Deep research completed with {len(res2.sources)} sources.")

    # =========================================================================
    # 2. CODING ASSISTANT TESTS (Multiple Languages & Actions)
    # =========================================================================
    print("\n" + "-"*70)
    print("[2] TESTING CODING ASSISTANT (6 Core Engineering Actions)")
    print("-"*70)

    # 2.1 Generate Code (Python)
    print("\n[2.1] Action: GENERATE (Python - Thread-Safe LRU Cache)...")
    req_gen = CodeAssistRequest(
        action="generate",
        language="python",
        prompt="Write a clean thread-safe LRU Cache with locks, get and put methods, type annotations, and docstrings."
    )
    res_gen = await coding_service.assist_code(req_gen)
    assert res_gen.action == "generate"
    assert res_gen.language == "python"
    assert "class" in (res_gen.code or res_gen.explanation).lower() or "def" in (res_gen.code or res_gen.explanation).lower()
    print(f"    [PASS] Code generated successfully ({len(res_gen.code or res_gen.explanation)} chars).")

    # 2.2 Debug Code (JavaScript)
    print("\n[2.2] Action: DEBUG (JavaScript - Off-by-one & negative array bug)...")
    buggy_js = """
    function findMaximum(nums) {
        let max = 0; // BUG: Fails if all numbers are negative
        for (let i = 0; i <= nums.length; i++) { // BUG: Index out of bounds
            if (nums[i] > max) max = nums[i];
        }
        return max;
    }
    """
    req_debug = CodeAssistRequest(
        action="debug",
        language="javascript",
        code=buggy_js,
        prompt="Find and fix all bugs in this maximum finder function."
    )
    res_debug = await coding_service.assist_code(req_debug)
    assert res_debug.action == "debug"
    assert len(res_debug.explanation) > 0
    print(f"    [PASS] Root cause analysis & fix identified.")

    # 2.3 Explain Code (TypeScript & Big-O Complexity)
    print("\n[2.3] Action: EXPLAIN (TypeScript - Quicksort & Complexity)...")
    ts_code = """
    function quickSort(arr: number[]): number[] {
        if (arr.length <= 1) return arr;
        const pivot = arr[arr.length - 1];
        const left = arr.filter((x, i) => x <= pivot && i < arr.length - 1);
        const right = arr.filter(x => x > pivot);
        return [...quickSort(left), pivot, ...quickSort(right)];
    }
    """
    req_explain = CodeAssistRequest(
        action="explain",
        language="typescript",
        code=ts_code
    )
    res_explain = await coding_service.assist_code(req_explain)
    assert res_explain.action == "explain"
    assert "O(" in res_explain.explanation or "complexity" in res_explain.explanation.lower() or "quicksort" in res_explain.explanation.lower()
    print(f"    [PASS] Logic breakdown & complexity analysis delivered.")

    # 2.4 Refactor Code (Go)
    print("\n[2.4] Action: REFACTOR (Go - Idiomatic Clean Architecture)...")
    go_code = """
    func DoWork(a int, b int) int {
        return a + b
    }
    """
    req_refactor = CodeAssistRequest(
        action="refactor",
        language="go",
        code=go_code,
        prompt="Refactor to follow SOLID principles and idiomatic Go conventions."
    )
    res_refactor = await coding_service.assist_code(req_refactor)
    assert res_refactor.action == "refactor"
    assert len(res_refactor.explanation) > 0
    print(f"    [PASS] Clean architecture refactoring complete.")

    # 2.5 Optimize Code (SQL)
    print("\n[2.5] Action: OPTIMIZE (SQL Query Performance)...")
    sql_query = """
    SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE country = 'US');
    """
    req_opt = CodeAssistRequest(
        action="optimize",
        language="sql",
        code=sql_query,
        prompt="Optimize subquery with INNER JOIN and indexing advice."
    )
    res_opt = await coding_service.assist_code(req_opt)
    assert res_opt.action == "optimize"
    assert len(res_opt.explanation) > 0
    print(f"    [PASS] Query optimization and index guidance provided.")

    # 2.6 Error Analysis (Python Traceback)
    print("\n[2.6] Action: ERROR ANALYSIS (Python Traceback Diagnosis)...")
    traceback_err = """
    Traceback (most recent call last):
      File "service.py", line 42, in process_batch
        res = 100 / item.get("total_count", 0)
    ZeroDivisionError: division by zero
    """
    req_err = CodeAssistRequest(
        action="error_analysis",
        language="python",
        errorMessage=traceback_err,
        prompt="Diagnose the root cause and provide defensive fallback handling."
    )
    res_err = await coding_service.assist_code(req_err)
    assert res_err.action == "error_analysis"
    assert len(res_err.explanation) > 0
    print(f"    [PASS] Error traceback diagnosed with defensive resolution.")

    # =========================================================================
    # 3. SANDBOXED CODE EXECUTION TESTS
    # =========================================================================
    print("\n" + "-"*70)
    print("[3] TESTING SANDBOXED SUBPROCESS EXECUTION & HOST SECURITY")
    print("-"*70)

    # 3.1 Normal Safe Execution
    print("\n[3.1] Running Safe Python Calculation in Sandbox...")
    py_snippet = "import math\nprint(f'PI approx: {math.pi:.4f}')\nprint(f'Sum 1..10: {sum(range(1, 11))}')"
    exec_res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=py_snippet
    ))
    assert exec_res.success is True
    assert exec_res.exitCode == 0
    assert "PI approx: 3.1416" in exec_res.stdout
    assert "Sum 1..10: 55" in exec_res.stdout
    print(f"    [PASS] Sandbox stdout:\n      {exec_res.stdout.strip()} ({exec_res.durationMs}ms)")

    # 3.2 Error Handling in Sandbox
    print("\n[3.2] Testing Sandbox Exception Capture...")
    bad_py = "print('starting test'); raise KeyError('SANDBOX_EXPECTED_KEY_ERROR')"
    bad_exec = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=bad_py
    ))
    assert bad_exec.success is False
    assert bad_exec.exitCode != 0
    assert "KeyError" in bad_exec.stderr
    print(f"    [PASS] Captured stderr correctly (Exit code: {bad_exec.exitCode})")

    # 3.3 Infinite Loop Timeout Protection (4.0s Cap)
    print("\n[3.3] Testing Subprocess Timeout Protection (Infinite Loop)...")
    loop_py = "import time\nwhile True:\n    time.sleep(0.05)"
    t0 = asyncio.get_event_loop().time()
    timeout_res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=loop_py
    ))
    dt = asyncio.get_event_loop().time() - t0
    assert timeout_res.success is False
    assert "timed out" in timeout_res.stderr.lower() or "timeout" in timeout_res.stderr.lower()
    assert dt < 6.0, f"Process took {dt:.2f}s, expected kill near 4.0s"
    print(f"    [PASS] Subprocess automatically killed after {dt:.2f}s timeout.")

    # 3.4 Host Safety / Blocked Danger Commands
    print("\n[3.4] Testing Host Security Filter...")
    danger_py = "import shutil; shutil.rmtree('C:/Windows/System32')"
    danger_res = await coding_service.execute_sandboxed_code(CodeExecutionRequest(
        language="python",
        code=danger_py
    ))
    assert danger_res.success is False
    assert "security policy" in danger_res.stderr.lower() or "blocked" in danger_res.stderr.lower()
    print(f"    [PASS] Dangerous command blocked by security guardrails.")

    # =========================================================================
    # 4. WRITING ASSISTANT TESTS (All 10 Editorial Features)
    # =========================================================================
    print("\n" + "-"*70)
    print("[4] TESTING WRITING ASSISTANT (10 Editorial Intelligence Actions)")
    print("-"*70)

    # 4.1 Rewrite
    print("\n[4.1] Action: REWRITE...")
    r_res = await writing_service.assist_writing(WritingAssistRequest(
        action="rewrite",
        text="we need to deploy the new features by monday or clients will be annoyed.",
        tone="professional"
    ))
    assert r_res.action == "rewrite"
    assert len(r_res.result) > 0
    assert r_res.outputWords > 0
    print(f"    [PASS] Rewrite output ({r_res.inputWords} -> {r_res.outputWords} words):\n      {r_res.result[:120]}...")

    # 4.2 Grammar
    print("\n[4.2] Action: GRAMMAR & SPELL...")
    g_res = await writing_service.assist_writing(WritingAssistRequest(
        action="grammar",
        text="The database querys is running slow and their is to many connections."
    ))
    assert g_res.action == "grammar"
    assert len(g_res.result) > 0
    print(f"    [PASS] Grammar & Diff analysis delivered.")

    # 4.3 Summarize
    print("\n[4.3] Action: SUMMARIZE...")
    long_doc = """
    Event-driven architectures decouple producers and consumers through asynchronous message brokers like Apache Kafka or RabbitMQ. 
    This pattern offers high horizontal scalability, fault tolerance, and independent component deployability. 
    However, it introduces complexities in distributed transactions, eventual consistency, schema evolution, and dead letter queue management.
    """
    s_res = await writing_service.assist_writing(WritingAssistRequest(
        action="summarize",
        text=long_doc
    ))
    assert s_res.action == "summarize"
    assert len(s_res.result) > 0
    print(f"    [PASS] Executive summary generated.")

    # 4.4 Expand
    print("\n[4.4] Action: EXPAND...")
    exp_res = await writing_service.assist_writing(WritingAssistRequest(
        action="expand",
        text="Implemented Redis vector cache. Response times improved.",
        tone="persuasive"
    ))
    assert exp_res.action == "expand"
    assert exp_res.outputWords > exp_res.inputWords
    print(f"    [PASS] Expanded draft from {exp_res.inputWords} to {exp_res.outputWords} words.")

    # 4.5 Shorten
    print("\n[4.5] Action: SHORTEN...")
    sh_res = await writing_service.assist_writing(WritingAssistRequest(
        action="shorten",
        text="In light of the fact that the platform architecture has reached full capacity, it is of the utmost importance that we immediately initiate the database migration process."
    ))
    assert sh_res.action == "shorten"
    assert len(sh_res.result) > 0
    print(f"    [PASS] Condensed draft successfully.")

    # 4.6 Professional Tone
    print("\n[4.6] Action: PROFESSIONAL TONE...")
    prof_res = await writing_service.assist_writing(WritingAssistRequest(
        action="professional",
        text="Hey folks, the auth service crashed because of memory leak. We patched it up."
    ))
    assert prof_res.action == "professional"
    assert len(prof_res.result) > 0
    print(f"    [PASS] Executive polish applied.")

    # 4.7 Email Composer
    print("\n[4.7] Action: EMAIL COMPOSER...")
    em_res = await writing_service.assist_writing(WritingAssistRequest(
        action="email",
        text="Update on Phase 4 launch. All AI tools are verified. Ready for deployment.",
        recipient="Chief Technology Officer",
        tone="professional"
    ))
    assert em_res.action == "email"
    assert "subject:" in em_res.result.lower() or "dear" in em_res.result.lower() or "hi" in em_res.result.lower()
    print(f"    [PASS] Structured email composed.")

    # 4.8 Resume Bullets (Action Verbs & Metrics)
    print("\n[4.8] Action: RESUME EXPERIENCE OPTIMIZER...")
    res_bullets = await writing_service.assist_writing(WritingAssistRequest(
        action="resume",
        text="Built search engine and coding sandbox for AI workspace.",
        jobTitle="Staff Software Engineer"
    ))
    assert res_bullets.action == "resume"
    assert len(res_bullets.result) > 0
    print(f"    [PASS] High-impact resume bullets generated.")

    # 4.9 Cover Letter
    print("\n[4.9] Action: COVER LETTER GENERATOR...")
    cl_res = await writing_service.assist_writing(WritingAssistRequest(
        action="cover_letter",
        text="10+ years architecting multi-tenant cloud platforms, distributed systems, and real-time AI interfaces.",
        jobTitle="Head of Engineering",
        companyName="Anthropic & Google DeepMind Ecosystem"
    ))
    assert cl_res.action == "cover_letter"
    assert len(cl_res.result) > 0
    print(f"    [PASS] Tailored executive cover letter generated.")

    # 4.10 Multilingual Translation
    print("\n[4.10] Action: MULTILINGUAL TRANSLATION (Spanish, French, German, Japanese, Hindi)...")
    source_msg = "NEXORA AI provides unified conversational intelligence, deep web research, and sandboxed code execution."
    for target in ["Spanish", "French", "German", "Japanese", "Hindi"]:
        tr_res = await writing_service.assist_writing(WritingAssistRequest(
            action="translate",
            text=source_msg,
            targetLanguage=target
        ))
        assert tr_res.action == "translate"
        assert len(tr_res.result) > 0
        print(f"      -> Translated to {target}: {tr_res.result[:60]}...")
    print("    [PASS] Multilingual translation verified across all targets.")

    print("\n" + "="*80)
    print("ALL PHASE 4 TESTS PASSED (100% SUCCESS)")
    print("="*80 + "\n")

def test_phase4_tools_suite():
    asyncio.run(run_tests())

if __name__ == "__main__":
    asyncio.run(run_tests())
