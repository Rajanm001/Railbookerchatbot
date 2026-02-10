"""
Health check and utility routes.
Production-grade probes for Kubernetes/load-balancer readiness.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import time
import logging

from app.db.database import get_db
from app.core.rate_limiting import limiter, HEALTH_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Track startup time for uptime reporting
_STARTUP_TIME = time.time()


@router.get("/")
@limiter.limit(HEALTH_LIMIT)
async def health_check(request: Request, db: Session = Depends(get_db)):
    """
    Check system health: database connectivity, package count, uptime.
    Safe when db is None (graceful degradation).
    """
    uptime_s = int(time.time() - _STARTUP_TIME)
    health = {
        "status": "healthy",
        "database": "unavailable",
        "packages": 0,
        "uptime_seconds": uptime_s,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if db is None:
        health["status"] = "degraded"
        health["database"] = "unavailable"
        return health

    try:
        result = db.execute(text("SELECT COUNT(*) FROM rag_packages")).scalar()
        health["database"] = "available"
        health["packages"] = result or 0
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health["status"] = "degraded"

    return health


@router.get("/ready")
@limiter.limit(HEALTH_LIMIT)
async def readiness_check(request: Request, db: Session = Depends(get_db)):
    """Returns 200 only when database is accessible. Safe when db is None."""
    if db is None:
        return {"ready": False, "error": "database unavailable", "timestamp": datetime.utcnow().isoformat()}
    try:
        db.execute(text("SELECT 1"))
        return {"ready": True, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return {"ready": False, "error": str(e)}


@router.get("/live")
async def liveness_check():
    """Liveness probe. Returns 200 if service is running."""
    return {"alive": True, "uptime_seconds": int(time.time() - _STARTUP_TIME), "timestamp": datetime.utcnow().isoformat()}
