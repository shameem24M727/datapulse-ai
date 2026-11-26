import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger("datapulse.db")

active_db_type = "unknown"

def _is_production_env() -> bool:
    return (
        os.getenv("RENDER", "").lower() == "true"
        or os.getenv("ENVIRONMENT", "").lower() == "production"
        or not settings.DEBUG
    )

def get_engine():
    global active_db_type
    primary_url = settings.DATABASE_URL
    if primary_url.startswith("postgres://"):
        primary_url = primary_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif primary_url.startswith("postgresql://"):
        primary_url = primary_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    try:
        # Attempt PostgreSQL connection check
        if primary_url.startswith("postgresql"):
            eng = create_engine(primary_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            active_db_type = "postgresql"
            logger.info("Connected successfully to PostgreSQL database.")
            return eng
    except Exception as e:
        if _is_production_env():
            logger.error(f"Production PostgreSQL connection failed ({type(e).__name__}). SQLite fallback is disabled in production.")
            raise RuntimeError(
                "Production PostgreSQL connection failed. Ephemeral SQLite fallback is disabled in production."
            ) from e
        logger.warning(f"PostgreSQL connection failed ({type(e).__name__}). Falling back to local SQLite database.")

    if _is_production_env() and not primary_url.startswith("sqlite"):
        raise RuntimeError(
            "Production environment requires a valid PostgreSQL DATABASE_URL. Ephemeral SQLite fallback is disabled."
        )

    # Local SQLite Fallback
    fallback_url = settings.SQLITE_FALLBACK_URL
    eng = create_engine(fallback_url, connect_args={"check_same_thread": False, "timeout": 30})
    
    # Configure WAL mode and busy timeout for concurrent read/write stability
    try:
        from sqlalchemy import event
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=15000")
                cursor.close()
            except Exception:
                pass
    except Exception:
        pass

    active_db_type = "sqlite"
    logger.info(f"Initialized local database at {fallback_url} with WAL mode.")
    return eng

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_status() -> dict:
    global active_db_type
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return {
                "status": "connected",
                "dialect": active_db_type,
                "url": "postgresql://***" if active_db_type == "postgresql" else settings.SQLITE_FALLBACK_URL,
            }
    except Exception as exc:
        return {
            "status": "disconnected",
            "dialect": active_db_type,
            "error": str(exc),
        }
