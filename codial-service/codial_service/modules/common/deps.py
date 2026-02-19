from __future__ import annotations

from fastapi import HTTPException, Request, status

from codial_service.app.codial_rules import CodialRuleStore
from codial_service.app.providers.catalog import get_enabled_provider_names
from codial_service.app.session_service import SessionService
from codial_service.app.settings import Settings, settings
from codial_service.app.store import InMemorySessionStore
from codial_service.app.turn_worker import TurnWorkerPool
from codial_service.modules.sessions.service import SessionsService
from codial_service.modules.turns.service import TurnsService


def get_settings(request: Request) -> Settings:
    configured = getattr(request.app.state, "settings", None)
    if isinstance(configured, Settings):
        return configured
    return settings


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


def get_sessions_service(request: Request) -> SessionsService:
    return SessionsService(
        store=get_store(request),
        session_defaults_service=get_session_service(request),
        enabled_provider_names=enabled_provider_names(request),
        workspace_root=get_settings(request).workspace_root,
    )


def get_turns_service(request: Request) -> TurnsService:
    return TurnsService(
        store=get_store(request),
        worker_pool=get_worker_pool(request),
    )
