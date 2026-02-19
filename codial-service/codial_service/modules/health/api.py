from __future__ import annotations

from fastapi import APIRouter, Request

from codial_service.modules.common.deps import get_worker_pool

router = APIRouter()


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(request: Request) -> dict[str, str]:
    get_worker_pool(request)
    return {"status": "ok"}
