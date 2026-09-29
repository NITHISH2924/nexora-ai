from fastapi import APIRouter, Depends, Request, HTTPException, status
from typing import List
from backend.app.models import (
    UserResponse,
    ChangePasswordRequest,
    MessageResponse,
    ActivityLogResponse
)
from backend.app.deps import get_current_user
from backend.app.services.user_service import user_service, row_to_user_dict

router = APIRouter(prefix="/api/user", tags=["User Profile"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    return row_to_user_dict(current_user)

@router.post("/change-password", response_model=MessageResponse)
async def change_password(data: ChangePasswordRequest, request: Request, current_user: dict = Depends(get_current_user)):
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    await user_service.change_password(
        user_id=current_user["userId"],
        data=data,
        ip_address=client_ip,
        user_agent=user_agent
    )
    return {
        "success": True,
        "message": "Password changed successfully"
    }

@router.get("/activity", response_model=List[ActivityLogResponse])
async def get_activity_log(current_user: dict = Depends(get_current_user)):
    logs = await user_service.get_user_activity(current_user["userId"], limit=20)
    return logs

@router.delete("/account", response_model=MessageResponse)
@router.post("/delete-account", response_model=MessageResponse)
async def delete_account(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    await user_service.delete_user_account(user_id=current_user["userId"])
    return {
        "success": True,
        "message": "User account and all associated data permanently deleted"
    }

