"""
Voice Agent — Logging Configuration
Structured logging with latency tracking middleware for FastAPI.
"""

import logging
import time
from fastapi import Request

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("voice_agent")

# Paths to skip in latency logging (reduce noise from static assets)
_SKIP_PATHS = {"/static/", "/favicon.ico"}


async def log_latency_middleware(request: Request, call_next):
    """Log request latency for API endpoints, skipping static file noise."""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000

    # Skip logging for static assets
    if not any(request.url.path.startswith(p) for p in _SKIP_PATHS):
        logger.info(
            "Method=%s Path=%s StatusCode=%s Latency=%.2fms",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )

    return response
