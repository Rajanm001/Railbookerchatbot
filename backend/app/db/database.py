"""
Database connection and session management.
Production-grade engine with connection pooling,
health-checked connections, and automatic recycling.
Supports PostgreSQL and SQLite backends.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from typing import Generator
import logging
import os

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

# Track database availability to avoid repeated slow connection attempts
_db_available = True  # Assume available until proven otherwise
_db_last_check = 0.0
_DB_RETRY_INTERVAL = 30  # Re-check every 30 seconds when DB is down

# Determine if using SQLite
_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    # SQLite: use StaticPool for thread safety, enable WAL mode
    # Resolve relative path to backend directory
    db_path = settings.database_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), db_path[2:])
        db_url = f"sqlite:///{db_path}"
    else:
        db_url = settings.database_url

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL: production pooling
    _connect_args = {
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000",
    }

    engine = create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle,
        pool_pre_ping=settings.database_pool_pre_ping,
        pool_timeout=30,
        echo=False,
        connect_args=_connect_args,
    )

    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Configure connection-level settings."""
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("SET application_name = 'railbookers-planner'")
            cursor.close()
        except Exception:
            pass

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session | None, None, None]:
    """
    Dependency injection for database session.
    Returns None if database is unavailable (graceful degradation).
    Caches unavailability status to avoid repeated slow connection attempts.
    """
    global _db_available, _db_last_check
    import time as _time

    # If DB was previously unavailable, yield None immediately
    # and only re-check every _DB_RETRY_INTERVAL seconds
    if not _db_available:
        now = _time.time()
        if now - _db_last_check < _DB_RETRY_INTERVAL:
            yield None
            return
        # Time to re-check
        _db_last_check = now

    db = None
    try:
        db = SessionLocal()
        yield db
        _db_available = True
    except Exception as e:
        logger.warning(f"Database unavailable: {e}")
        _db_available = False
        _db_last_check = _time.time()
        yield None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def init_db() -> None:
    """Initialize database tables at startup."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized")
