from __future__ import annotations

from codial_service.modules import build_api_router

router = build_api_router()

__all__ = ["router"]
