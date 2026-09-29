import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.deps import get_current_user
from backend.app.models import (
    UserPreferencesRequest,
    UserPreferencesResponse,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryItemResponse,
    MemoryListResponse
)
from backend.app.services.personalization_service import personalization_service

logger = logging.getLogger("routes.personalization")
router = APIRouter(prefix="/api/personalization", tags=["Personalization & Controlled Memory"])

# ------------------------------------------------------------------------------
# User Preferences Endpoints
# ------------------------------------------------------------------------------

@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(current_user: dict = Depends(get_current_user)):
    """Get personalization and AI preference settings for the authenticated user."""
    user_id = current_user["userId"]
    return await personalization_service.get_preferences(user_id)

@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    req: UserPreferencesRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update personalization and AI preference settings."""
    user_id = current_user["userId"]
    return await personalization_service.update_preferences(user_id, req)

# ------------------------------------------------------------------------------
# Controlled Memory Architecture Endpoints
# ------------------------------------------------------------------------------

@router.get("/memories", response_model=MemoryListResponse)
async def list_user_memories(current_user: dict = Depends(get_current_user)):
    """List all retained memories and knowledge items for the authenticated user."""
    user_id = current_user["userId"]
    return await personalization_service.list_memories(user_id)

@router.post("/memories", response_model=MemoryItemResponse)
async def create_user_memory(
    req: MemoryCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new transparent memory item."""
    user_id = current_user["userId"]
    return await personalization_service.create_memory(user_id, req)

@router.patch("/memories/{memory_id}", response_model=MemoryItemResponse)
async def update_user_memory(
    memory_id: str,
    req: MemoryUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update or toggle active state of a specific memory item."""
    user_id = current_user["userId"]
    return await personalization_service.update_memory(user_id, memory_id, req)

@router.delete("/memories/{memory_id}")
async def delete_user_memory(
    memory_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific memory item."""
    user_id = current_user["userId"]
    deleted = await personalization_service.delete_memory(user_id, memory_id)
    return {"message": "Memory item deleted successfully", "id": memory_id, "success": deleted}

@router.delete("/memories")
async def clear_all_user_memories(current_user: dict = Depends(get_current_user)):
    """Purge and clear all retained memories for the authenticated user."""
    user_id = current_user["userId"]
    cleared = await personalization_service.clear_all_memories(user_id)
    return {"message": "All memories purged successfully", "success": cleared}
