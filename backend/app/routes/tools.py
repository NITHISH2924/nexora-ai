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
    WritingAssistResponse,
    VideoPlanRequest,
    VideoPlanResponse,
    LearningAssistRequest,
    LearningAssistResponse
)
from backend.app.services.search_service import search_service
from backend.app.services.coding_service import coding_service
from backend.app.services.writing_service import writing_service
from backend.app.services.ai_providers.manager import ai_manager

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

# ----------------------------------------------------------------------
# 4. AI VIDEO STUDIO (Script, Storyboard & Scene Planning)
# ----------------------------------------------------------------------
@router.post("/video/plan", response_model=VideoPlanResponse)
async def plan_video(
    req: VideoPlanRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Phase 4: AI Video Studio Storyboard & Scene Planner:
    - Generates multi-scene storyboard breakdown
    - Specifies visual direction, framing, camera movement, and duration
    - Compiles synchronized audio voiceover narration script
    - Clearly indicates external video rendering requirements (Runway, Luma, Replicate)
    """
    prompt = (
        f"You are the NEXORA AI Video Studio Director. Plan a professional video production for:\n"
        f"Topic: {req.topic}\n"
        f"Style: {req.style}\n"
        f"Target Duration: {req.durationSeconds} seconds\n"
        f"Target Audience: {req.targetAudience}\n\n"
        f"Provide a comprehensive, high-quality production plan with:\n"
        f"1. A catchy video title.\n"
        f"2. 4 distinct visual scenes with scene numbers, visual descriptions, shot types, and estimated scene duration in seconds.\n"
        f"3. A complete voiceover audio narration script."
    )

    sys_prompt = "You are NEXORA AI Video Production Studio. Produce structured, highly cinematic video plans."
    messages = [{"role": "user", "content": prompt}]
    ai_text, _ = await ai_manager.generate_response(messages=messages, model=req.model or "nexora-smart-router", system_prompt=sys_prompt)

    # Structure scenes
    scenes = [
        {
            "sceneNumber": 1,
            "title": "Opening Hook & Establishing Scene",
            "shotType": "Wide Cinematic Dolly-In",
            "visualDescription": f"Establishing visuals illustrating the theme of '{req.topic}'. High dynamic range, atmospheric lighting in {req.style} aesthetic.",
            "durationSeconds": max(5, int(req.durationSeconds * 0.2))
        },
        {
            "sceneNumber": 2,
            "title": "Core Concept Introduction",
            "shotType": "Medium Close-Up with Motion Graphics",
            "visualDescription": f"Dynamic presentation highlighting key aspects of {req.topic}. Smooth pan and focal depth transition.",
            "durationSeconds": max(8, int(req.durationSeconds * 0.35))
        },
        {
            "sceneNumber": 3,
            "title": "Deep Dive & Key Highlights",
            "shotType": "Detail Shot / Macro Focus",
            "visualDescription": "Detailed visual showcase with subtle text overlays emphasizing key learning points.",
            "durationSeconds": max(8, int(req.durationSeconds * 0.3))
        },
        {
            "sceneNumber": 4,
            "title": "Climax & Call-To-Action",
            "shotType": "Wide Pull-Out with Brand Outro",
            "visualDescription": "Memorable final sequence leading to concluding takeaway and visual brand crest.",
            "durationSeconds": max(4, int(req.durationSeconds * 0.15))
        }
    ]

    return VideoPlanResponse(
        topic=req.topic,
        style=req.style or "cinematic",
        durationSeconds=req.durationSeconds or 60,
        title=f"{req.topic.title()} — {req.style.title()} Production",
        scenes=scenes,
        audioScript=ai_text,
        externalProviderRequired=True,
        providerStatus="Video storyboard and voiceover script generated. Direct video pixel generation requires configuring RUNWAY_API_KEY or REPLICATE_API_TOKEN."
    )

# ----------------------------------------------------------------------
# 5. AI LEARNING HUB (Tutoring, Quizzes, Flashcards & Study Plans)
# ----------------------------------------------------------------------
@router.post("/learning/assist", response_model=LearningAssistResponse)
async def learning_assist(
    req: LearningAssistRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Phase 4: AI Learning Hub:
    - quiz: Generate practice exam questions with detailed explanations
    - flashcards: Key conceptual revision cards
    - study_plan: Structured pedagogical roadmap
    - tutor_explain: Clear step-by-step beginner-friendly technical explanation
    """
    context_note = f"\nDocument Context:\n{req.documentContext[:4000]}\n" if req.documentContext else ""
    prompt = (
        f"You are the NEXORA AI Master Tutor. Perform the educational action '{req.action}' on:\n"
        f"Topic: {req.topic}\n"
        f"Learner Level: {req.level}\n"
        f"{context_note}\n"
        f"Deliver structured, rigorous, and easy-to-follow study material with clear headings, examples, and takeaways."
    )

    sys_prompt = "You are NEXORA AI Learning Hub. Provide clear, encouraging, pedagogically sound educational assistance."
    messages = [{"role": "user", "content": prompt}]
    ai_text, _ = await ai_manager.generate_response(messages=messages, model=req.model or "nexora-smart-router", system_prompt=sys_prompt)

    action_titles = {
        "quiz": f"Practice Quiz & Knowledge Check: {req.topic}",
        "flashcards": f"Revision Flashcards: {req.topic}",
        "study_plan": f"Personalized Mastery Roadmap: {req.topic}",
        "tutor_explain": f"Step-by-Step AI Tutoring: {req.topic}"
    }

    return LearningAssistResponse(
        action=req.action,
        topic=req.topic,
        level=req.level or "beginner",
        title=action_titles.get(req.action, f"Learning Material: {req.topic}"),
        content=ai_text,
        metadata={"learnerLevel": req.level, "questionCount": req.questionCount}
    )

