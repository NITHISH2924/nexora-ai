import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from backend.app.deps import get_current_user
from backend.app.models import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectNoteCreateRequest,
    ProjectNoteUpdateRequest,
    ProjectNoteResponse,
    ProjectSavedOutputCreateRequest,
    ProjectSavedOutputResponse,
    ProjectAssociateItemRequest,
    ProjectSummary,
    ProjectDetail
)
from backend.app.services.project_service import project_service

logger = logging.getLogger("routes.projects")
router = APIRouter(prefix="/api/projects", tags=["Project Workspace"])

@router.post("", response_model=ProjectSummary)
async def create_project(
    req: ProjectCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new project workspace."""
    user_id = current_user["userId"]
    return await project_service.create_project(user_id, req)

@router.get("", response_model=List[ProjectSummary])
async def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """List all projects for the authenticated user."""
    user_id = current_user["userId"]
    return await project_service.list_projects(user_id, limit=limit, offset=offset)

@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get project details with associated chats, files, notes, and saved outputs."""
    user_id = current_user["userId"]
    return await project_service.get_project(user_id, project_id)

@router.patch("/{project_id}", response_model=ProjectSummary)
async def update_project(
    project_id: str,
    req: ProjectUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update project metadata (name, description, instructions, color)."""
    user_id = current_user["userId"]
    return await project_service.update_project(user_id, project_id, req)

@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a project and its notes, outputs, and item associations."""
    user_id = current_user["userId"]
    deleted = await project_service.delete_project(user_id, project_id)
    return {"message": "Project deleted successfully", "id": project_id, "success": deleted}

# ------------------------------------------------------------------------------
# Project Notes Endpoints
# ------------------------------------------------------------------------------

@router.post("/{project_id}/notes", response_model=ProjectNoteResponse)
async def add_project_note(
    project_id: str,
    req: ProjectNoteCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add a note to a project."""
    user_id = current_user["userId"]
    return await project_service.add_note(user_id, project_id, req)

@router.get("/{project_id}/notes", response_model=List[ProjectNoteResponse])
async def list_project_notes(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """List notes within a project."""
    user_id = current_user["userId"]
    return await project_service.list_notes(user_id, project_id)

@router.patch("/{project_id}/notes/{note_id}", response_model=ProjectNoteResponse)
async def update_project_note(
    project_id: str,
    note_id: str,
    req: ProjectNoteUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update a project note."""
    user_id = current_user["userId"]
    return await project_service.update_note(user_id, project_id, note_id, req)

@router.delete("/{project_id}/notes/{note_id}")
async def delete_project_note(
    project_id: str,
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a note from a project."""
    user_id = current_user["userId"]
    deleted = await project_service.delete_note(user_id, project_id, note_id)
    return {"message": "Note deleted successfully", "id": note_id, "success": deleted}

# ------------------------------------------------------------------------------
# Project Saved Outputs Endpoints
# ------------------------------------------------------------------------------

@router.post("/{project_id}/outputs", response_model=ProjectSavedOutputResponse)
async def save_project_output(
    project_id: str,
    req: ProjectSavedOutputCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save an AI output to a project."""
    user_id = current_user["userId"]
    return await project_service.save_output(user_id, project_id, req)

@router.get("/{project_id}/outputs", response_model=List[ProjectSavedOutputResponse])
async def list_project_saved_outputs(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """List saved outputs in a project."""
    user_id = current_user["userId"]
    return await project_service.list_saved_outputs(user_id, project_id)

@router.delete("/{project_id}/outputs/{output_id}")
async def delete_project_saved_output(
    project_id: str,
    output_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a saved output from a project."""
    user_id = current_user["userId"]
    deleted = await project_service.delete_saved_output(user_id, project_id, output_id)
    return {"message": "Output deleted successfully", "id": output_id, "success": deleted}

# ------------------------------------------------------------------------------
# Project Item Associations Endpoints (Link/Unlink Chats and Files)
# ------------------------------------------------------------------------------

@router.post("/{project_id}/items")
async def associate_project_item(
    project_id: str,
    req: ProjectAssociateItemRequest,
    current_user: dict = Depends(get_current_user)
):
    """Link a chat or file to a project workspace."""
    user_id = current_user["userId"]
    return await project_service.associate_item(user_id, project_id, req.itemType, req.itemId)

@router.delete("/{project_id}/items/{item_type}/{item_id}")
async def remove_project_item(
    project_id: str,
    item_type: str,
    item_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Unlink a chat or file from a project."""
    user_id = current_user["userId"]
    deleted = await project_service.remove_associated_item(user_id, project_id, item_type, item_id)
    return {"message": "Item unlinked from project successfully", "success": deleted}
