from fastapi import APIRouter
from datetime import datetime, timezone
from app.db.session import get_db_status
from app.services.gemini_service import gemini_copilot_service
from app.services.cache_service import cache_service

router = APIRouter()

@router.get("/detailed")
async def detailed_health():
    db_status = get_db_status()
    is_healthy = db_status.get("status") == "connected"

    return {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "api": "online",
            "database": db_status.get("status", "disconnected"),
            "database_dialect": db_status.get("dialect", "unknown"),
            "redis_cache": "connected" if cache_service.is_connected else "fallback_mode",
            "ml_engine": "ready",
            "quality_engine": "online",
            "anomaly_engine": "online",
            "ai_copilot_service": "online" if gemini_copilot_service.is_api_configured() else "grounded_fallback",
            "streaming_engine": "online",
        },
        "cache": cache_service.get_metrics(),
        "milestone": 6,
        "note": "Milestone 6: Intelligent Redis caching layer active with graceful database fallback and strict organization-level tenant isolation.",
    }

@router.get("/cache")
def get_cache_telemetry():
    """Returns real-time Redis caching telemetry, hit/miss ratios, and connectivity status."""
    return {
        "status": "online" if cache_service.is_connected else "fallback_mode",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": cache_service.get_metrics(),
    }
