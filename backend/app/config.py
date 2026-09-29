import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables (.env.production if present, else .env)
app_env = os.getenv("APP_ENV", "development").lower()
if app_env == "production" and (BASE_DIR / ".env.production").exists():
    load_dotenv(BASE_DIR / ".env.production", override=True)
else:
    load_dotenv(BASE_DIR / ".env")

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "NEXORA AI")
    APP_ENV: str = os.getenv("APP_ENV", "development").lower()
    HOST: str = os.getenv("HOST", "0.0.0.0" if os.getenv("APP_ENV") == "production" else "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://127.0.0.1:8000").rstrip("/")
    PRODUCTION_DOMAIN: str = os.getenv("PRODUCTION_DOMAIN", "").strip()

    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "nexora_default_secret_key_change_in_production_2026")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) # 24h
    SECURE_COOKIES: bool = os.getenv("SECURE_COOKIES", "false" if APP_ENV != "production" else "true").lower() in ("true", "1", "yes")

    # CORS
    CORS_ORIGINS: list = [
        orig.strip() for orig in os.getenv("CORS_ORIGINS", f"{FRONTEND_URL},http://localhost:8000,http://127.0.0.1:8000").split(",") if orig.strip()
    ]

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/nexora.db")

    # Official Leadership & Identity
    OWNER_NAME: str = "Nithish Kumar R"
    CEO_NAME: str = "Dhanushiya S"
    OWNER_EMAIL: str = os.getenv("OWNER_EMAIL", "owner@nexora.ai").strip().lower()
    CEO_EMAIL: str = os.getenv("CEO_EMAIL", "ceo@nexora.ai").strip().lower()
    LEADERSHIP_RESPONSE: str = "The Owner is Nithish Kumar R and the CEO is Dhanushiya S."

    # System Identity Prompt for all AI Providers
    SYSTEM_IDENTITY_PROMPT: str = (
        "You are NEXORA AI, a world-class unified AI intelligence platform. "
        "OFFICIAL LEADERSHIP IDENTITY & RESPONSE MANDATE:\n"
        "- The Owner of NEXORA AI is Nithish Kumar R.\n"
        "- The CEO of NEXORA AI is Dhanushiya S.\n"
        "- CRITICAL RULE: If a user asks ANY question related to the Owner, CEO, founder, creator, or leadership of NEXORA AI, "
        "you MUST ALWAYS answer with BOTH roles together using the exact wording:\n"
        "\"The Owner is Nithish Kumar R and the CEO is Dhanushiya S.\"\n"
        "Never mention one without the other, and never attribute ownership or leadership to anyone else."
    )

    # Rate limiting
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30"))

    # Email
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "no-reply@nexora.ai")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # File Uploads & Storage
    UPLOAD_DIR: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "data/uploads")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_MB", "20")) * 1024 * 1024

    # Allowed extensions & MIME types
    ALLOWED_EXTENSIONS: set = {
        ".pdf", ".docx", ".txt", ".csv",
        ".png", ".jpg", ".jpeg", ".webp", ".gif"
    }
    ALLOWED_MIME_TYPES: set = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif"
    }

    # AI Providers & Keys (Server-Side Only - Never Exposed to Frontend)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")).strip()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    DEFAULT_AI_MODEL: str = os.getenv("DEFAULT_AI_MODEL", "gemini-1.5-flash")

settings = Settings()

def is_leadership_query(text: str) -> bool:
    """Detects if a user query is asking about the Owner, CEO, founder, creator, or leadership of NEXORA AI."""
    import re
    if not text or not isinstance(text, str):
        return False
    t = text.lower().strip()
    
    # Direct exact/short question patterns
    exact_matches = {
        "who is the owner", "who is the owner?",
        "who is the ceo", "who is the ceo?",
        "who is owner", "who is owner?",
        "who is ceo", "who is ceo?",
        "who owns nexora", "who owns nexora?",
        "who owns nexora ai", "who owns nexora ai?",
        "who is the ceo of nexora", "who is the ceo of nexora?",
        "who is the ceo of nexora ai", "who is the ceo of nexora ai?",
        "who created nexora", "who created nexora?",
        "who created nexora ai", "who created nexora ai?",
        "tell me about the leadership of nexora ai", "tell me about the leadership of nexora ai?",
        "tell me about the leadership of nexora", "tell me about the leadership of nexora?",
        "tell me about the leadership", "tell me about the leadership?",
        "who is your owner", "who is your owner?",
        "who is your ceo", "who is your ceo?",
        "who is your creator", "who is your creator?",
        "who is your founder", "who is your founder?",
        "who owns this", "who owns this?",
        "who owns this app", "who owns this app?",
        "who created this", "who created this?",
        "who founded this", "who founded this?",
        "who made nexora", "who made nexora?",
        "who made nexora ai", "who made nexora ai?",
        "owner", "ceo", "leadership"
    }
    if t in exact_matches:
        return True
        
    regex_patterns = [
        r"\b(who|tell me about|what is the name of|names? of)\b.*\b(owner|ceo|founder|creator|leadership|leaders|running|built|created|founded|owns)\b",
        r"\b(who owns|who created|who founded|who made|who runs)\b",
        r"\b(who is (the |your )?(owner|ceo|founder|creator))\b",
        r"\b(owner|ceo|founder|creator|leadership)\b.*\b(nexora|platform|app|company|system)\b",
        r"\b(nexora|platform|app|company|system)\b.*\b(owner|ceo|founder|creator|leadership)\b"
    ]
    for p in regex_patterns:
        if re.search(p, t, re.IGNORECASE):
            return True
    return False

