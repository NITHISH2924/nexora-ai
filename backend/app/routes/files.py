import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Response
from fastapi.responses import FileResponse

from backend.app.deps import get_current_user
from backend.app.models import (
    FileSummary,
    FileDetail,
    FileAIActionRequest,
    FileAIActionResponse,
    ImageAnalysisRequest,
    ImageAnalysisResponse
)
from backend.app.services.file_service import file_service

logger = logging.getLogger("routes.files")
router = APIRouter(prefix="/api/files", tags=["Files & Document Intelligence"])

@router.post("/upload", response_model=FileDetail)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload and process a document (PDF, DOCX, TXT, CSV) or image with isolation."""
    user_id = current_user["userId"]
    return await file_service.save_uploaded_file(user_id=user_id, upload_file=file)

@router.get("", response_model=List[FileSummary])
async def list_files(
    q: Optional[str] = Query(None, description="Search by filename or content"),
    fileType: Optional[str] = Query(None, description="Filter by type: pdf, docx, txt, csv, image"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """List authenticated user's uploaded files."""
    return await file_service.get_user_files(
        user_id=current_user["userId"],
        query=q,
        file_type=fileType,
        limit=limit,
        offset=offset
    )

@router.get("/{file_id}", response_model=FileDetail)
async def get_file_detail(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get file details, extracted text, and summary."""
    return await file_service.get_file(user_id=current_user["userId"], file_id=file_id)

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a file from database and disk storage."""
    await file_service.delete_file(user_id=current_user["userId"], file_id=file_id)
    return {"success": True, "message": "File deleted successfully", "fileId": file_id}

@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Securely download file with attachment headers."""
    user_id = current_user["userId"]
    file_data = await file_service.get_file(user_id=user_id, file_id=file_id)
    disk_path = await file_service.get_file_disk_path(user_id=user_id, file_id=file_id)

    return FileResponse(
        path=disk_path,
        media_type=file_data["mimeType"],
        filename=file_data["originalFilename"]
    )

@router.post("/{file_id}/ai-action", response_model=FileAIActionResponse)
async def document_ai_action(
    file_id: str,
    req: FileAIActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute AI Document Intelligence:
    - summarize: Structured executive summary
    - qa: Grounded Q&A over document text
    - extract: Structured figures, entities, tables
    - explain: Plain-language concept breakdown
    - notes: High-yield study & executive notes
    - questions: Review & quiz question generator
    """
    return await file_service.execute_document_ai_action(
        user_id=current_user["userId"],
        file_id=file_id,
        action=req.action,
        query=req.query,
        model=req.model,
        system_prompt=req.systemPrompt
    )

@router.post("/vision/analyze", response_model=ImageAnalysisResponse)
async def vision_image_analysis(
    req: ImageAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute Multimodal Vision & Image Analysis:
    - describe: In-depth visual scene description
    - screenshot: UI breakdown, error/code transcription, UX review
    - ocr: Precise text transcription & table parsing
    - diagram: Architecture / flowchart / graph explanation
    - qa: Custom questions answered from image context
    """
    return await file_service.execute_image_analysis(
        user_id=current_user["userId"],
        file_id=req.fileId,
        image_base64=req.imageBase64,
        action=req.action or "describe",
        query=req.query,
        model=req.model
    )
