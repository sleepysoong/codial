from __future__ import annotations

from fastapi import HTTPException, Request, status

from codial_service.app.codial_rules import CodialRuleStore
from codial_service.app.settings import Settings, settings
from codial_service.modules.sessions.service import SessionService
from codial_service.modules.turns.service import TurnsService
from codial_service.modules.turns.worker import TurnWorkerPool


def get_settings(request: Request) -> Settings:
    configured = getattr(request.app.state, "settings", None)
    if isinstance(configured, Settings):
        return configured
    return settings


def require_auth(request: Request, authorization: str) -> None:
    if authorization != f"Bearer {get_settings(request).api_token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했어요.")


def get_rule_store(request: Request) -> CodialRuleStore:
    rule_store = getattr(request.app.state, "codial_rule_store", None)
    if not isinstance(rule_store, CodialRuleStore):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="규칙 저장소를 사용할 수 없어요.")
    return rule_store


def get_worker_pool(request: Request) -> TurnWorkerPool:
    worker_pool = getattr(request.app.state, "turn_worker_pool", None)
    if not isinstance(worker_pool, TurnWorkerPool):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="작업 워커를 사용할 수 없어요.")
    return worker_pool


def get_session_service(request: Request) -> SessionService:
    session_service = getattr(request.app.state, "session_service", None)
    if not isinstance(session_service, SessionService):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="세션 서비스를 사용할 수 없어요.")
    return session_service


def get_turns_service(request: Request) -> TurnsService:
    turns_service = getattr(request.app.state, "turns_service", None)
    if not isinstance(turns_service, TurnsService):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="턴 서비스를 사용할 수 없어요.")
    return turns_service
