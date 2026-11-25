from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional, Union
import os

class Settings(BaseSettings):
    APP_NAME: str = "DataPulse AI"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = True
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://datapulse-ai-zeta.vercel.app",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/datapulse_ai"
    SQLITE_FALLBACK_URL: str = "sqlite:///./datapulse.db"

    # Seeding & Demo Configuration
    SEED_DEMO_USERS: bool = False
    ADMIN_INITIAL_PASSWORD: Optional[str] = None
    DEMO_ENGINEER_PASSWORD: Optional[str] = None
    DEMO_VIEWER_PASSWORD: Optional[str] = None

    # Ingestion
    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
    ALLOWED_EXTENSIONS: List[str] = ["csv", "xlsx", "xls"]

    # Google Gemini AI Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_REQUEST_TIMEOUT_SECONDS: int = 25

    # Security & Authentication (Milestone 5)
    JWT_SECRET_KEY: str = "datapulse_ai_super_secret_jwt_key_for_milestone_5_change_in_production_min32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    # Redis Caching (Milestone 6)
    REDIS_ENABLED: bool = True
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_TIMEOUT_SECONDS: float = 1.0
    REDIS_KEY_PREFIX: str = "datapulse"

    # Cache TTL Defaults (in seconds)
    CACHE_TTL_OVERVIEW_SUMMARY: int = 60
    CACHE_TTL_DATASET_LIST: int = 120
    CACHE_TTL_DATASET_DETAIL: int = 300
    CACHE_TTL_PIPELINE_LIST: int = 30
    CACHE_TTL_PIPELINE_DETAIL: int = 30
    CACHE_TTL_PIPELINE_METRICS: int = 15
    CACHE_TTL_PIPELINE_ALERTS: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Ensure uploads directory exists safely
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
