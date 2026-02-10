"""
Core configuration module for the Railbookers Rail Vacation Planner.
Production-grade settings with environment variable management.
Developed by Rajan Mishra.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Production-ready with sensible defaults.
    """

    # Application
    app_name: str = "Railbookers Rail Vacation Planner"
    app_version: str = "2.0.0"
    environment: str = "production"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/rail_planner"
    database_pool_size: int = 25
    database_max_overflow: int = 50
    database_pool_recycle: int = 1800  # Recycle connections after 30 min
    database_pool_pre_ping: bool = True  # Verify connections before use

    # RAG Configuration
    rag_max_tokens: int = 2048
    rag_retrieval_top_k: int = 5
    rag_similarity_threshold: float = 0.7

    # API Configuration
    api_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8890
    api_workers: int = 4

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # CORS - restrict to known frontend origins (extend via .env)
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8890"]
    cors_allow_credentials: bool = False
    cors_allow_methods: list = ["GET", "POST", "OPTIONS"]
    cors_allow_headers: list = ["Content-Type", "Accept", "Accept-Language", "X-API-Key"]

    # Session Management
    session_ttl_minutes: int = 30
    max_concurrent_sessions: int = 10000

    # Admin API key for protected endpoints (MUST be set via .env in production)
    admin_api_key: str = "CHANGE-ME-IN-DOTENV"

    # Enforce that the app uses only real data (no demo/fallback mode)
    # When True, endpoints will return 503 if DB is unavailable instead of
    # serving fallback/demo data. Set to False to allow graceful degradation.
    enforce_real_data: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
