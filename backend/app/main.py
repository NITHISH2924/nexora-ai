from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import settings, BASE_DIR
from backend.app.database import create_tables
from backend.app.routes.auth import router as auth_router
from backend.app.routes.user import router as user_router
from backend.app.routes.owner import router as owner_router
from backend.app.routes.chat import router as chat_router
from backend.app.routes.files import router as files_router
from backend.app.routes.tools import router as tools_router
from backend.app.routes.images import router as images_router
from backend.app.routes.voice import router as voice_router
from backend.app.routes.projects import router as projects_router
from backend.app.routes.personalization import router as personalization_router

FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database & tables exist
    await create_tables()
    yield
    # Shutdown: Cleanup if needed

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-Ready AI Platform Authentication & Core Foundation",
    version="1.0.0",
    lifespan=lifespan
)

# Production CORS configuration
cors_origins = list(set(settings.CORS_ORIGINS + [settings.FRONTEND_URL, "http://localhost:8000", "http://127.0.0.1:8000"]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Include API Routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(owner_router)
app.include_router(chat_router)
app.include_router(files_router)
app.include_router(tools_router)
app.include_router(images_router)
app.include_router(voice_router)
app.include_router(projects_router)
app.include_router(personalization_router)

# Company & Leadership Public Information Endpoint
@app.get("/api/company/leadership", tags=["Company Leadership"])
async def get_company_leadership():
    """Returns official executive leadership info for NEXORA AI."""
    return {
        "company": settings.APP_NAME,
        "owner": settings.OWNER_NAME,
        "ceo": settings.CEO_NAME,
        "ownerEmail": settings.OWNER_EMAIL,
        "ceoEmail": settings.CEO_EMAIL,
        "standardAnswer": settings.LEADERSHIP_RESPONSE
    }



# Mount static asset folders if they exist
if (FRONTEND_DIR / "css").exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
if (FRONTEND_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

# Page Routes (Clean URLs)
@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/login")
async def serve_login():
    return FileResponse(FRONTEND_DIR / "login.html")

@app.get("/signup")
async def serve_signup():
    return FileResponse(FRONTEND_DIR / "signup.html")

@app.get("/forgot-password")
async def serve_forgot_password():
    return FileResponse(FRONTEND_DIR / "forgot-password.html")

@app.get("/reset-password")
async def serve_reset_password():
    return FileResponse(FRONTEND_DIR / "reset-password.html")

@app.get("/verify-email")
async def serve_verify_email():
    return FileResponse(FRONTEND_DIR / "verify-email.html")

@app.get("/app")
async def serve_app():
    return FileResponse(FRONTEND_DIR / "app.html")

@app.get("/admin")
async def serve_admin():
    return FileResponse(FRONTEND_DIR / "app.html")

@app.get("/privacy")
async def serve_privacy():
    return FileResponse(FRONTEND_DIR / "privacy.html")

@app.get("/terms")
async def serve_terms():
    return FileResponse(FRONTEND_DIR / "terms.html")

@app.get("/delete-account")
async def serve_delete_account():
    return FileResponse(FRONTEND_DIR / "delete-account.html")


import logging

logger = logging.getLogger("main")

# Global Exception Handlers for clean sanitized error responses (no stack trace exposure)
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "detail": exc.detail},
        headers=exc.headers
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "detail": "An internal server error occurred. Please try again later."}
    )

