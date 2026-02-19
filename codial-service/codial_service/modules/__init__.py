from __future__ import annotations

from fastapi import APIRouter


def build_api_router() -> APIRouter:
    from codial_service.modules.health.api import router as health_router
    from codial_service.modules.rules.api import router as rules_router
    from codial_service.modules.sessions.api import router as sessions_router
    from codial_service.modules.turns.api import router as turns_router

    api_router = APIRouter(prefix="/v1")
    api_router.include_router(sessions_router)
    api_router.include_router(rules_router)
    api_router.include_router(turns_router)
    api_router.include_router(health_router)
    return api_router


__all__ = ["build_api_router"]
