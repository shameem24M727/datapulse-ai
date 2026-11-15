import sys
import asyncio
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import get_db_status
from app.services.websocket_manager import websocket_manager

# Ensure DB tables are initialized
try:
    init_db()
except Exception as e:
    print(f"Database initialization notice: {e}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="DataPulse AI — Intelligent Data Quality & Pipeline Observability Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

@app.on_event("startup")
async def startup_event():
    try:
        websocket_manager.set_event_loop(asyncio.get_running_loop())
    except Exception as e:
        print(f"WebSocket loop init notice: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health", tags=["Health"])
async def health_check():
    db_status = get_db_status()
    return {
        "status": "healthy" if db_status.get("status") == "connected" else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "milestone": 3,
        "database": db_status,
    }
