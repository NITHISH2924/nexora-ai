import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.deps import get_current_user
from backend.app.models import (
    SearchRequest,
    SearchResponse,
    CodeAssistRequest,
    CodeAssistResponse,
    CodeExecutionRequest,
    CodeExecutionResponse,
    WritingAssistRequest,
    WritingAssistResponse
)
from backend.app.services.search_service import search_service
from backend.app.services.coding_service import coding_service
from backend.app.services.writing_service import writing_service

logger = logging.getLogger("routes.tools")
router = APIRouter(prefix="/api/tools", tags=["AI Tools & Intelligence Assistants"])

# ----------------------------------------------------------------------
# 1. AI DEEP SEARCH
# ----------------------------------------------------------------------
@router.post("/search", response_model=SearchResponse)
async def ai_search(
    req: SearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute AI Deep Search:
    - Queries search provider
    - Retrieves grounded web context
    - Generates factual AI synthesis with numbered citations [1], [2]
    - Returns citations with real source metadata
    """
    return await search_service.search_and_synthesize(
        query=req.query,
        max_results=req.maxResults,
        model=req.model,
        search_depth=req.searchDepth or "standard"
    )

# ----------------------------------------------------------------------
# 2. CODING ASSISTANT & SANDBOXED RUNNER
# ----------------------------------------------------------------------
@router.post("/code/assist", response_model=CodeAssistResponse)
async def code_assist(
    req: CodeAssistRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute AI Coding Assistance:
    - generate: Write clean, type-annotated code
    - debug: Find bugs and root causes with fixed code
    - explain: Step-by-step logic and Big-O complexity
    - refactor: Apply clean code, SOLID & DRY principles
    - optimize: Performance, latency and memory optimization
    - error_analysis: Diagnose error traces and logs
    """
    return await coding_service.assist_code(req)

@router.post("/code/execute", response_model=CodeExecutionResponse)
async def execute_code_sandboxed(
    req: CodeExecutionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute code inside a safe, isolated subprocess with timeout protection.
    Never executes arbitrary commands on production server.
    """
    return await coding_service.execute_sandboxed_code(req)

# ----------------------------------------------------------------------
# 3. WRITING ASSISTANT & TRANSLATION
# ----------------------------------------------------------------------
@router.post("/writing/assist", response_model=WritingAssistResponse)
async def writing_assist(
    req: WritingAssistRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute AI Writing Assistance:
    - rewrite, grammar, summarize, expand, shorten
    - professional business polish
    - email composer
    - resume experience optimizer
    - cover letter generator
    - multilingual translation
    """
    return await writing_service.assist_writing(req)
