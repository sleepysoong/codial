from __future__ import annotations

from fastapi import HTTPException, Request, status

from codial_service.app.codial_rules import CodialRuleStore
from codial_service.app.providers.catalog import get_enabled_provider_names
from codial_service.app.session_service import SessionService
from codial_service.app.settings import Settings, settings
from codial_service.app.store import InMemorySessionStore
from codial_service.app.turn_worker import TurnWorkerPool


def get_settings(request: Request) -> Settings:
    configured = getattr(request.app.state, "settings", None)
    return configured if isinstance(configured, Settings) else settings  # type: ignore[return-value]


def require_auth(request: Request, authorization: str) -> None:
    if authorization != f"Bearer {get_settings(request).api_token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했어요.")


def enabled_provider_names(request: Request) -> list[str]:
    app_settings = get_settings(request)
    return get_enabled_provider_names(
        app_settings.enabled_provider_names,
        fallback_default=app_settings.default_provider_name,
    )


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service  # type: ignore[no-any-return]


def get_store(request: Request) -> InMemorySessionStore:
    return request.app.state.store  # type: ignore[no-any-return]


def get_rule_store(request: Request) -> CodialRuleStore:
    return request.app.state.codial_rule_store  # type: ignore[no-any-return]


def get_worker_pool(request: Request) -> TurnWorkerPool:
    worker_pool = getattr(request.app.state, "turn_worker_pool", None)
    if not isinstance(worker_pool, TurnWorkerPool):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="작업 워커를 사용할 수 없어요.")
    return worker_pool
