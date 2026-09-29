from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from backend.app.models import (
    UserRegisterRequest,
    UserLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    UserResponse,
    AuthResponse,
    MessageResponse
)
from backend.app.services.user_service import user_service, row_to_user_dict
from backend.app.deps import get_current_user
from backend.app.security import rate_limiter
from backend.app.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

@router.post("/signup", response_model=AuthResponse)
async def signup(data: UserRegisterRequest, request: Request, response: Response):
    client_ip = get_client_ip(request)
    allowed, retry_after = rate_limiter.is_allowed(f"signup:{client_ip}", max_limit=10)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration attempts. Please try again in {retry_after} seconds."
        )

    user_agent = request.headers.get("User-Agent")
    user, token = await user_service.register_user(data, ip_address=client_ip, user_agent=user_agent)

    # Set httpOnly cookie for seamless session management
    is_secure = settings.SECURE_COOKIES or (settings.APP_ENV == "production") or (request.url.scheme == "https") or (request.headers.get("x-forwarded-proto") == "https")
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=is_secure
    )

    return {
        "user": user,
        "token": token,
        "tokenType": "Bearer",
        "message": "Registration successful. Verification email dispatched."
    }

@router.post("/login", response_model=AuthResponse)
async def login(data: UserLoginRequest, request: Request, response: Response):
    client_ip = get_client_ip(request)
    allowed, retry_after = rate_limiter.is_allowed(f"login:{client_ip}", max_limit=15)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please wait {retry_after} seconds before retrying."
        )

    user_agent = request.headers.get("User-Agent")
    user, token = await user_service.login_user(data, ip_address=client_ip, user_agent=user_agent)

    max_age = (30 * 86400) if data.rememberMe else (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    is_secure = settings.SECURE_COOKIES or (settings.APP_ENV == "production") or (request.url.scheme == "https") or (request.headers.get("x-forwarded-proto") == "https")
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=max_age,
        samesite="lax",
        secure=is_secure
    )

    return {
        "user": user,
        "token": token,
        "tokenType": "Bearer",
        "message": "Login successful"
    }

@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    response.delete_cookie(key="access_token")
    return {"success": True, "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_current_authenticated_user(current_user: dict = Depends(get_current_user)):
    return row_to_user_dict(current_user)

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(data: ForgotPasswordRequest, request: Request):
    client_ip = get_client_ip(request)
    allowed, retry_after = rate_limiter.is_allowed(f"forgot:{client_ip}", max_limit=5)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {retry_after} seconds."
        )

    user_agent = request.headers.get("User-Agent")
    await user_service.request_password_reset(data.email, ip_address=client_ip, user_agent=user_agent)
    return {
        "success": True,
        "message": "If an account exists with this email, a password reset link has been dispatched."
    }

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: ResetPasswordRequest, request: Request):
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    await user_service.reset_password(data, ip_address=client_ip, user_agent=user_agent)
    return {
        "success": True,
        "message": "Your password has been successfully reset. You can now log in with your new password."
    }

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(data: VerifyEmailRequest, request: Request):
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    await user_service.verify_email(data.token, ip_address=client_ip, user_agent=user_agent)
    return {
        "success": True,
        "message": "Your email address has been successfully verified."
    }

@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(current_user: dict = Depends(get_current_user)):
    if current_user["emailVerified"]:
        return {"success": True, "message": "Email is already verified."}
    await user_service.resend_verification(current_user["email"])
    return {"success": True, "message": "Verification email resent successfully."}
