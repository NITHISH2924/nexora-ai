import base64
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from fastapi.responses import FileResponse

from backend.app.deps import get_current_user
from backend.app.models import (
    VoiceTranscribeResponse,
    VoiceSynthesizeRequest,
    VoiceSynthesizeResponse,
    VoicePipelineRequest,
    VoicePipelineResponse,
    VoiceStatusResponse
)
from backend.app.services.voice_service import voice_service

logger = logging.getLogger("routes.voice")
router = APIRouter(prefix="/api/voice", tags=["Voice Intelligence & Audio Streaming"])

@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status(
    current_user: dict = Depends(get_current_user)
):
    """Check provider connectivity status and supported voice personas."""
    return voice_service.get_status()

@router.post("/transcribe", response_model=VoiceTranscribeResponse)
async def transcribe_audio_file(
    file: Optional[UploadFile] = File(None),
    audioBase64: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    current_user: dict = Depends(get_current_user)
):
    """
    Speech-to-Text: Transcribe voice audio recording to text.
    Supports direct audio file upload (WAV, WEBM, MP3) or Base64 payload.
    """
    audio_bytes: bytes = b""
    filename = "recording.wav"

    if file:
        audio_bytes = await file.read()
        filename = file.filename or "recording.wav"
    elif audioBase64:
        # Strip data URL prefix if present
        b64 = audioBase64
        if "base64," in b64:
            b64 = b64.split("base64,")[1]
        try:
            audio_bytes = base64.b64decode(b64)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Base64 audio encoding."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide audio file or audioBase64 payload."
        )

    return await voice_service.transcribe_audio(
        audio_bytes=audio_bytes,
        filename=filename,
        language=language
    )

@router.post("/synthesize", response_model=VoiceSynthesizeResponse)
async def synthesize_speech(
    req: VoiceSynthesizeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Text-to-Speech: Convert text prompt or AI response into playable audio.
    Supports voice personas: alloy, echo, fable, onyx, nova, shimmer.
    """
    user_id = current_user["userId"]
    return await voice_service.synthesize_speech(user_id, req)

@router.post("/pipeline", response_model=VoicePipelineResponse)
async def voice_pipeline(
    req: VoicePipelineRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Full Voice-to-Voice Pipeline:
    Speech Audio In → Speech-to-Text → NEXORA AI Reasoning → Text-to-Speech Audio Out.
    """
    user_id = current_user["userId"]
    if not req.audioBase64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="audioBase64 payload is required for voice pipeline."
        )

    b64 = req.audioBase64
    if "base64," in b64:
        b64 = b64.split("base64,")[1]

    try:
        audio_bytes = base64.b64decode(b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Base64 audio payload."
        )

    return await voice_service.execute_voice_pipeline(
        user_id=user_id,
        audio_bytes=audio_bytes,
        voice=req.voice or "alloy",
        model=req.model,
        system_prompt=req.systemPrompt
    )

@router.get("/audio/{audio_id}")
async def get_audio_stream(
    audio_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Stream or download synthesized speech WAV audio file."""
    user_id = current_user["userId"]
    file_path = await voice_service.get_audio_file_path(user_id, audio_id)
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"speech_{audio_id[:8]}.wav"
    )
