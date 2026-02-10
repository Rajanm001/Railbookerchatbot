"""
Railbookers Rail Vacation Planner -- FastAPI Application
Production-grade backend for high-concurrency deployment.
Developed by Rajan Mishra
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import logging.config
from datetime import datetime
import time
import asyncio

from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limiting import limiter, rate_limit_handler
from app.db.database import init_db
from app.api import health, routes_packages, routes_planner, routes_i18n

# Configure logging
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        },
    },
    "handlers": {
        "default": {
            "formatter": "detailed",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "app": {"handlers": ["default"], "level": settings.log_level},
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "sqlalchemy": {"handlers": ["default"], "level": "WARNING"},
    },
}

logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session cleanup background task
# ---------------------------------------------------------------------------
async def _session_cleanup_task():
    """Periodically evict expired sessions to prevent memory leaks."""
    ttl_seconds = settings.session_ttl_minutes * 60
    while True:
        await asyncio.sleep(120)  # Check every 2 minutes
        try:
            sessions = routes_planner.conversation_sessions
            now = time.time()
            expired = [
                sid for sid, s in sessions.items()
                if now - s.get("_ts", 0) > ttl_seconds
            ]
            for sid in expired:
                del sessions[sid]
            if expired:
                logger.info(f"Session cleanup: evicted {len(expired)} expired sessions, "
                           f"{len(sessions)} active")
        except Exception as e:
            logger.warning(f"Session cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment} | Workers: {settings.api_workers}")

    try:
        # Retry DB init up to 3 times for resilience
        for attempt in range(1, 4):
            try:
                init_db()
                logger.info("Database initialized successfully")
                break
            except Exception as e:
                if attempt < 3:
                    logger.warning(f"Database init attempt {attempt}/3 failed: {e}, retrying in 2s...")
                    await asyncio.sleep(2)
                else:
                    raise

        # Warm caches at startup for instant first responses
        try:
            from app.db.database import SessionLocal
            from app.services.db_options import warm_cache
            _warm_db = SessionLocal()
            warmed = warm_cache(_warm_db)
            _warm_db.close()
            logger.info(f"Cache warming complete: {warmed} lookups pre-loaded")
        except Exception as e:
            logger.warning(f"Cache warming skipped: {e}")
    except Exception as e:
        # If configured to enforce real data, abort startup rather than running in demo mode
        if settings.enforce_real_data:
            logger.error(f"Database init failed after 3 attempts and enforce_real_data=True, aborting startup: {e}")
            raise RuntimeError(f"Database init failed: {e}")
        # Otherwise allow graceful fallback (legacy behaviour)
        logger.warning(f"Database init failed after 3 attempts, running in demo mode: {e}")
        # Mark DB as unavailable so get_db() yields None instantly
        from app.db.database import _db_available
        import app.db.database as _db_mod
        import time as _time
        _db_mod._db_available = False
        _db_mod._db_last_check = _time.time()

    # Start session cleanup background task
    cleanup_task = asyncio.create_task(_session_cleanup_task())
    logger.info(f"Session TTL: {settings.session_ttl_minutes}m | "
                f"Max sessions: {settings.max_concurrent_sessions}")
    logger.info("Application startup complete -- ready to serve")

    yield

    # Shutdown
    cleanup_task.cancel()
    logger.info("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Railbookers Rail Vacation Planner -- Personalised package recommendations. Developed by Rajan Mishra.",
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# GZip compression (min 500 bytes)
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# Combined request logging + security headers middleware (single pass)
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Log requests with timing + add production security headers in one pass."""
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", "")

    response = await call_next(request)

    elapsed = time.perf_counter() - start
    # Timing header
    response.headers["X-Process-Time"] = f"{elapsed:.3f}"
    response.headers["X-Powered-By"] = "Railbookers"

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Dynamic CSP: allow self + configured CORS origins for connect-src
    allowed_origins = " ".join(settings.cors_origins)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        f"connect-src 'self' {allowed_origins}; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    if request_id:
        response.headers["X-Request-ID"] = request_id

    # Log non-static requests
    path = request.url.path
    if not path.startswith("/static"):
        logger.info(
            f"{request.method} {path} -> {response.status_code} in {elapsed:.3f}s"
        )

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions gracefully."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Include routers
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(routes_packages.router, prefix=settings.api_prefix)
app.include_router(routes_planner.router, prefix=settings.api_prefix)
app.include_router(routes_i18n.router, prefix=settings.api_prefix)


# Root endpoint
@app.get("/")
async def root():
    """Root -- API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "health": f"{settings.api_prefix}/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
