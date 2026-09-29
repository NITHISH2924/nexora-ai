from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from backend.app.models import (
    UserResponse,
    UserStatusUpdateRequest,
    UserRoleUpdateRequest,
    MessageResponse
)
from backend.app.config import settings
from backend.app.deps import get_current_owner
from backend.app.services.user_service import user_service
from backend.app.database import get_db

router = APIRouter(prefix="/api/owner", tags=["Owner Administration"])

@router.get("/overview")
async def get_system_overview(current_owner: dict = Depends(get_current_owner)):
    now_dt = datetime.now(timezone.utc)
    today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now_dt - timedelta(days=7)).isoformat()

    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) as count FROM users") as c:
            total_users = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM users WHERE accountCreatedAt >= ?", (today_start,)) as c:
            new_users_today = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM users WHERE accountCreatedAt >= ?", (week_start,)) as c:
            new_users_week = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM users WHERE accountStatus = 'ACTIVE'") as c:
            active_users = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM users WHERE emailVerified = 1") as c:
            verified_users = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM users WHERE accountStatus = 'SUSPENDED'") as c:
            suspended_users = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM users WHERE role = 'OWNER'") as c:
            owner_count = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM audit_logs") as c:
            total_events = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM audit_logs WHERE action = 'LOGIN'") as c:
            login_events = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM messages WHERE role = 'assistant'") as c:
            ai_requests = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM files") as c:
            file_uploads = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM generated_images") as c:
            image_generations = (await c.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) as count FROM audit_logs WHERE action LIKE '%SEARCH%'") as c:
            search_requests = (await c.fetchone())["count"]

    return {
        "ownerName": settings.OWNER_NAME,
        "ceoName": settings.CEO_NAME,
        "totalUsers": total_users,
        "newUsersToday": new_users_today,
        "newUsersThisWeek": new_users_week,
        "activeUsers": active_users,
        "verifiedUsers": verified_users,
        "suspendedUsers": suspended_users,
        "ownerCount": owner_count,
        "totalAuditEvents": total_events,
        "loginEvents": login_events,
        "aiRequests": ai_requests,
        "fileUploads": file_uploads,
        "searchRequests": search_requests,
        "imageGenerations": image_generations
    }

@router.get("/users", response_model=List[UserResponse])
async def list_all_users(
    q: Optional[str] = Query(None, description="Search users by email"),
    role: Optional[str] = Query(None, description="Filter by role: USER, OWNER"),
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, PENDING_VERIFICATION, SUSPENDED"),
    current_owner: dict = Depends(get_current_owner)
):
    users = await user_service.get_all_users_admin(search=q, role_filter=role, status_filter=status)
    return users

@router.get("/login-activity")
async def get_login_activity(
    limit: int = Query(50, ge=1, le=200),
    current_owner: dict = Depends(get_current_owner)
):
    """Retrieve audit login activity logs with device, time, and user email."""
    activity = await user_service.get_login_activity_admin(limit=limit)
    return {"activity": activity}

@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    data: UserStatusUpdateRequest,
    current_owner: dict = Depends(get_current_owner)
):
    updated = await user_service.update_user_status_admin(
        target_user_id=user_id,
        new_status=data.accountStatus,
        admin_user_id=current_owner["userId"]
    )
    return updated

@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    data: UserRoleUpdateRequest,
    current_owner: dict = Depends(get_current_owner)
):
    updated = await user_service.update_user_role_admin(
        target_user_id=user_id,
        new_role=data.role,
        admin_user_id=current_owner["userId"]
    )
    return updated
