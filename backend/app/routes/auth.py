from typing import Optional
from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.models import (
    UserRegisterRequest,
    UserLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    UserResponse,
    AuthResponse,
    LoginResponse,
    MessageResponse,
    MFAVerifyRequest,
    MFAEnableRequest,
    MFADisableRequest,
    MFASetupResponse
)
from backend.app.services.user_service import user_service, row_to_user_dict
from backend.app.deps import get_current_user
from backend.app.security import rate_limiter, auth_rate_limiter, get_client_ip
from backend.app.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer(auto_error=False)

@router.post("/signup", response_model=AuthResponse)
async def signup(data: UserRegisterRequest, request: Request, response: Response):
    client_ip = get_client_ip(request)
    allowed, retry_after = await auth_rate_limiter.check_and_increment_ip(
        client_ip=client_ip,
        action="signup",
        max_limit=10,
        window_seconds=getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
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

@router.post("/login", response_model=LoginResponse)
async def login(data: UserLoginRequest, request: Request, response: Response):
    client_ip = get_client_ip(request)
    ip_limit = getattr(settings, "AUTH_IP_MAX_LOGIN_ATTEMPTS", 10)
    allowed, retry_after = await auth_rate_limiter.check_and_increment_ip(
        client_ip=client_ip,
        action="login",
        max_limit=ip_limit,
        window_seconds=getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts from this network. Please wait {retry_after} seconds before retrying.",
            headers={"Retry-After": str(retry_after)}
        )

    user_agent = request.headers.get("User-Agent")
    user, token = await user_service.login_user(data, ip_address=client_ip, user_agent=user_agent)

    if user.get("mfaRequired"):
        return {
            "user": None,
            "token": None,
            "tokenType": None,
            "mfaRequired": True,
            "mfaSessionToken": token,
            "message": "Two-factor authentication code required"
        }

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
        "mfaRequired": False,
        "mfaSessionToken": None,
        "message": "Login successful"
    }

@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
):
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    if token:
        await user_service.revoke_session(
            token=token,
            user_id=current_user["userId"],
            reason="USER_LOGOUT",
            ip_address=client_ip,
            user_agent=user_agent
        )

    response.delete_cookie(key="access_token")
    return {"success": True, "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_current_authenticated_user(current_user: dict = Depends(get_current_user)):
    return row_to_user_dict(current_user)

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(current_user: dict = Depends(get_current_user)):
    data = await user_service.setup_mfa(current_user["userId"])
    return data

@router.post("/mfa/enable", response_model=MessageResponse)
async def mfa_enable(
    data: MFAEnableRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    await user_service.enable_mfa(
        user_id=current_user["userId"],
        secret=data.secret,
        code=data.code,
        recovery_codes=data.recoveryCodes,
        ip_address=client_ip,
        user_agent=user_agent
    )
    return {"success": True, "message": "Two-factor authentication successfully enabled"}

@router.post("/mfa/verify", response_model=AuthResponse)
async def mfa_verify(
    data: MFAVerifyRequest,
    request: Request,
    response: Response
):
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    user, token = await user_service.verify_mfa_login(
        mfa_session_token=data.mfaSessionToken,
        code=data.code,
        ip_address=client_ip,
        user_agent=user_agent
    )

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
        "message": "Two-factor authentication verified. Login successful."
    }

@router.post("/mfa/disable", response_model=MessageResponse)
async def mfa_disable(
    data: MFADisableRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    await user_service.disable_mfa(
        user_id=current_user["userId"],
        current_password=data.currentPassword,
        code=data.code,
        ip_address=client_ip,
        user_agent=user_agent
    )
    return {"success": True, "message": "Two-factor authentication disabled"}

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(data: ForgotPasswordRequest, request: Request):
    client_ip = get_client_ip(request)
    allowed, retry_after = await auth_rate_limiter.check_and_increment_ip(
        client_ip=client_ip,
        action="forgot",
        max_limit=5,
        window_seconds=getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
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
