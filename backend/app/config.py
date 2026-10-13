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
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", os.getenv("JWT_SECRET", "nexora_default_secret_key_change_in_production_2026"))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) # 24h
    SECURE_COOKIES: bool = os.getenv("SECURE_COOKIES", "false" if APP_ENV != "production" else "true").lower() in ("true", "1", "yes")

    # CORS
    _raw_cors = os.getenv("CORS_ORIGINS", f"{FRONTEND_URL},http://localhost:8000,http://127.0.0.1:8000")
    CORS_ORIGINS: list = [orig.strip() for orig in _raw_cors.split(",") if orig.strip()]

    # Trusted reverse proxies (Loopback, RFC 1918 Private networks, Cloudflare CGNAT)
    TRUSTED_PROXIES: list = [
        p.strip() for p in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10").split(",") if p.strip()
    ]

    def get_cors_allow_origins(self) -> list:
        origins = set(self.CORS_ORIGINS)
        if self.FRONTEND_URL:
            origins.add(self.FRONTEND_URL.rstrip("/"))
        if self.PRODUCTION_DOMAIN:
            origins.add(f"https://{self.PRODUCTION_DOMAIN}".rstrip("/"))
            origins.add(f"https://app.{self.PRODUCTION_DOMAIN}".rstrip("/"))
        origins.update([
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://10.0.2.2:8000",
            "capacitor://localhost",
            "http://localhost",
            "https://localhost"
        ])
        return sorted([o for o in origins if o])

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

    # Stage 3: Authentication, Session & Brute Force Defense
    AUTH_MAX_FAILED_ATTEMPTS: int = int(os.getenv("AUTH_MAX_FAILED_ATTEMPTS", "5"))
    AUTH_LOCKOUT_DURATION_SECONDS: int = int(os.getenv("AUTH_LOCKOUT_DURATION_SECONDS", "300")) # 5 min lockout
    AUTH_IP_MAX_LOGIN_ATTEMPTS: int = int(os.getenv("AUTH_IP_MAX_LOGIN_ATTEMPTS", "10"))
    REQUIRE_OWNER_MFA: bool = os.getenv("REQUIRE_OWNER_MFA", "true").lower() in ("true", "1", "yes")
    MFA_TEMP_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("MFA_TEMP_TOKEN_EXPIRE_MINUTES", "5"))

    # Code Execution Sandbox Hardening
    ENABLE_CODE_EXECUTION: bool = os.getenv("ENABLE_CODE_EXECUTION", "true").lower() in ("true", "1", "yes")
    CODE_EXECUTION_TIMEOUT_SECONDS: float = float(os.getenv("CODE_EXECUTION_TIMEOUT_SECONDS", "4.0"))
    MAX_CODE_OUTPUT_BYTES: int = int(os.getenv("MAX_CODE_OUTPUT_BYTES", "65536")) # 64 KB safety buffer
    MAX_CODE_INPUT_BYTES: int = int(os.getenv("MAX_CODE_INPUT_BYTES", "65536"))   # 64 KB input buffer limit
    MAX_CONCURRENT_CODE_EXECUTIONS: int = int(os.getenv("MAX_CONCURRENT_CODE_EXECUTIONS", "4"))
    CODE_SANDBOX_WORKER_URL: str = os.getenv("CODE_SANDBOX_WORKER_URL", "").strip()
    REQUIRE_CONTAINER_SANDBOX_IN_PROD: bool = os.getenv("REQUIRE_CONTAINER_SANDBOX_IN_PROD", "true").lower() in ("true", "1", "yes")

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
    # Normalize punctuation and extra spaces
    normalized = re.sub(r'[^a-z0-9\s]', '', t).strip()
    
    # Direct exact/short question patterns
    exact_matches = {
        "who is the owner", "who is the ceo",
        "who is owner", "who is ceo",
        "who owns nexora", "who owns nexora ai",
        "who is the ceo of nexora", "who is the ceo of nexora ai",
        "who is the owner of nexora", "who is the owner of nexora ai",
        "who created nexora", "who created nexora ai",
        "tell me about the leadership of nexora ai", "tell me about the leadership of nexora",
        "tell me about the leadership",
        "tell me about the ceo of nexora ai", "tell me about the owner of nexora ai",
        "tell me about the ceo", "tell me about the owner",
        "who are the owner and ceo", "who is the owner and ceo",
        "who is the owner and who is the ceo",
        "who is the owner or ceo", "who is owner and ceo",
        "who is the owner and ceo of this app",
        "who is the owner of this app", "who is the ceo of this app",
        "who is your owner", "who is your ceo",
        "who is your creator", "who is your founder",
        "who is your boss", "who is the boss",
        "who owns this", "who owns this app",
        "who created this", "who created this app",
        "who founded this", "who founded this app",
        "who made nexora", "who made nexora ai",
        "who made this app", "who made this",
        "owner", "ceo", "leadership", "founder", "creator"
    }
    if normalized in exact_matches or t in exact_matches:
        return True
        
    regex_patterns = [
        r"\b(who|tell me|what|names?)\b.*\b(owner|ceo|founder|creator|leadership|leaders|boss|running|built|created|founded|owns)\b",
        r"\b(who owns|who created|who founded|who made|who runs)\b",
        r"\b(who (is|are) (the |your )?(owner|ceo|founder|creator|leadership|leaders|boss))\b",
        r"\b(owner|ceo|founder|creator|leadership)\b.*\b(nexora|platform|app|company|system)\b",
        r"\b(nexora|platform|app|company|system)\b.*\b(owner|ceo|founder|creator|leadership)\b",
        r"\b(nexoras|nexora's)\s+(owner|ceo|founder|creator|leadership|boss)\b",
        r"\b(owner|ceo)\b.*\b(nexoras|nexora's)\b",
        r"\b(owner\s+(and|or|&)\s+ceo|ceo\s+(and|or|&)\s+owner)\b"
    ]
    for p in regex_patterns:
        if re.search(p, t, re.IGNORECASE) or re.search(p, normalized, re.IGNORECASE):
            return True
    return False

