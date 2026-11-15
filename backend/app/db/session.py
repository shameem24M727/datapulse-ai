import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger("datapulse.db")

active_db_type = "unknown"

def get_engine():
    global active_db_type
    primary_url = settings.DATABASE_URL
    try:
        # Attempt PostgreSQL connection check
        if primary_url.startswith("postgresql"):
            eng = create_engine(primary_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            active_db_type = "postgresql"
            logger.info("Connected successfully to PostgreSQL database.")
            return eng
    except Exception as e:
        logger.warning(f"PostgreSQL connection to {primary_url} failed ({e}). Falling back to local SQLite database.")

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
