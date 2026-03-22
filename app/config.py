import logging
import time
from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── CONFIGURATION ───
class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./data/appointments.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# ─── LOGGING ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("voice_agent")

_SKIP_PATHS = {"/static/", "/favicon.ico"}

async def log_latency_middleware(request: Request, call_next):
    """Log request latency for API endpoints, skipping static file noise."""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000

    if not any(request.url.path.startswith(p) for p in _SKIP_PATHS):
        logger.info(
            "Method=%s Path=%s StatusCode=%s Latency=%.2fms",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )

    return response
