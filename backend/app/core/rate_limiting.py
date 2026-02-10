"""
Rate Limiting & Throttling
Production-grade request throttling per IP.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


# Rate limit definitions
SEARCH_LIMIT = "100/minute"
PLANNER_LIMIT = "120/minute"
RECOMMENDATION_LIMIT = "60/minute"
HEALTH_LIMIT = "1000/minute"


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 JSON response when rate limit exceeded."""
    client_host = request.client.host if request.client else "unknown"
    logger.warning(f"Rate limit exceeded for {client_host}: {request.url.path}")

    return JSONResponse(
        status_code=429,
        content={
            "error": "too_many_requests",
            "message": f"Rate limit exceeded. Please slow down.",
            "retry_after": 60,
        },
        headers={"Retry-After": "60"},
    )
