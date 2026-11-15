from fastapi import APIRouter
from app.api.v1.endpoints import health, datasets, overview, copilot, pipelines, auth, organizations

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations & Multi-Tenancy"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(overview.router, prefix="/overview", tags=["Overview"])
api_router.include_router(copilot.router, prefix="/copilot", tags=["AI Copilot"])
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["Pipelines & Streaming"])
