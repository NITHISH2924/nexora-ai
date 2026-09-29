import uvicorn
from backend.app.config import settings

if __name__ == "__main__":
    print(f"[*] Starting {settings.APP_NAME} server on http://{settings.HOST}:{settings.PORT}")
    print(f"[*] App Environment: {settings.APP_ENV}")
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True if settings.APP_ENV == "development" else False
    )
