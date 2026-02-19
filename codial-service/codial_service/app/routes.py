from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status

from codial_service.app.codial_rules import CodialRuleStore
from codial_service.app.models import (
    BindChannelRequest,
    BindChannelResponse,
    CodialRuleAddRequest,
    CodialRuleRemoveRequest,
    CodialRuleResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionResponse,
    SessionConfigResponse,
    SetMcpRequest,
    SetModelRequest,
    SetProviderRequest,
    SetSubagentRequest,
    SubmitTurnRequest,
)
from codial_service.app.policy_loader import PolicyLoader, extract_agent_defaults
from codial_service.app.providers.catalog import (
    choose_default_provider,
    get_enabled_provider_names,
)
from codial_service.app.settings import settings
from codial_service.app.store import InMemorySessionStore
from codial_service.app.subagent_spec import default_subagent_search_paths, discover_subagents
from codial_service.app.turn_worker import TurnWorkerPool
from libs.common.logging import get_logger

router = APIRouter(prefix="/v1")
logger = get_logger("codial_service.routes")


def _check_auth(authorization: str) -> None:
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했어요.")


def _load_subagent_names() -> set[str]:
    specs = discover_subagents(default_subagent_search_paths(settings.workspace_root))
    return {spec.name for spec in specs}


def _enabled_provider_names() -> list[str]:
    return get_enabled_provider_names(
        settings.enabled_provider_names,
        fallback_default=settings.default_provider_name,
    )


def _get_store(request: Request) -> InMemorySessionStore:
    return request.app.state.store  # type: ignore[no-any-return]


def _get_policy_loader(request: Request) -> PolicyLoader:
    return request.app.state.policy_loader  # type: ignore[no-any-return]


def _get_rule_store(request: Request) -> CodialRuleStore:
    return request.app.state.codial_rule_store  # type: ignore[no-any-return]


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: Request,
    req: CreateSessionRequest,
    authorization: str = Header(default=""),
) -> CreateSessionResponse:
    _check_auth(authorization)

    policy_snapshot = _get_policy_loader(request).load()
    agent_defaults = extract_agent_defaults(policy_snapshot.agents_text)
    default_provider = choose_default_provider(agent_defaults.provider, _enabled_provider_names())
    record = await _get_store(request).create_session(
        req.guild_id,
        req.requester_id,
        req.idempotency_key,
        default_provider=default_provider,
        default_model=agent_defaults.model or "gpt-5-mini",
        default_mcp_enabled=agent_defaults.mcp_enabled if agent_defaults.mcp_enabled is not None else True,
        default_mcp_profile_name=agent_defaults.mcp_profile_name or "default",
    )
    logger.info("session_created", session_id=record.session_id, guild_id=req.guild_id)
    return CreateSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/bind-channel", response_model=BindChannelResponse)
async def bind_channel(
    request: Request,
    session_id: str,
    req: BindChannelRequest,
    authorization: str = Header(default=""),
) -> BindChannelResponse:
    _check_auth(authorization)
    try:
        record = await _get_store(request).bind_channel(session_id=session_id, channel_id=req.channel_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc

    return BindChannelResponse(
        session_id=record.session_id,
        channel_id=req.channel_id,
        status=record.status,
    )


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_session(
    request: Request,
    session_id: str,
    authorization: str = Header(default=""),
) -> EndSessionResponse:
    _check_auth(authorization)
    try:
        record = await _get_store(request).end_session(session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return EndSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/provider", response_model=SessionConfigResponse)
async def set_provider(
    request: Request,
    session_id: str,
    req: SetProviderRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    _check_auth(authorization)

    enabled_providers = set(_enabled_provider_names())
    if req.provider not in enabled_providers:
        enabled_text = ", ".join(sorted(enabled_providers))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 사용할 수 없는 프로바이더예요. 사용 가능 목록: {enabled_text}",
        )

    try:
        record = await _get_store(request).set_provider(session_id=session_id, provider=req.provider)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
        subagent_name=record.subagent_name,
    )


@router.post("/sessions/{session_id}/model", response_model=SessionConfigResponse)
async def set_model(
    request: Request,
    session_id: str,
    req: SetModelRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    _check_auth(authorization)
    try:
        record = await _get_store(request).set_model(session_id=session_id, model=req.model)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
        subagent_name=record.subagent_name,
    )


@router.post("/sessions/{session_id}/mcp", response_model=SessionConfigResponse)
async def set_mcp(
    request: Request,
    session_id: str,
    req: SetMcpRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    _check_auth(authorization)
    try:
        record = await _get_store(request).set_mcp(
            session_id=session_id,
            enabled=req.enabled,
            profile_name=req.profile_name,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
        subagent_name=record.subagent_name,
    )


@router.post("/sessions/{session_id}/subagent", response_model=SessionConfigResponse)
async def set_subagent(
    request: Request,
    session_id: str,
    req: SetSubagentRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    _check_auth(authorization)

    requested_name = req.name.strip() if isinstance(req.name, str) else ""
    normalized_name = requested_name if requested_name else None
    if normalized_name is not None:
        available_names = _load_subagent_names()
        if normalized_name not in available_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="서브에이전트를 찾을 수 없어요.",
            )

    try:
        record = await _get_store(request).set_subagent(session_id=session_id, subagent_name=normalized_name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc

    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
        subagent_name=record.subagent_name,
    )


@router.get("/codial/rules", response_model=CodialRuleResponse)
async def list_codial_rules(
    request: Request,
    authorization: str = Header(default=""),
) -> CodialRuleResponse:
    _check_auth(authorization)
    return CodialRuleResponse(rules=_get_rule_store(request).list_rules())


@router.post("/codial/rules", response_model=CodialRuleResponse)
async def add_codial_rule(
    request: Request,
    req: CodialRuleAddRequest,
    authorization: str = Header(default=""),
) -> CodialRuleResponse:
    _check_auth(authorization)
    return CodialRuleResponse(rules=_get_rule_store(request).add_rule(req.rule))


@router.delete("/codial/rules", response_model=CodialRuleResponse)
async def remove_codial_rule(
    request: Request,
    req: CodialRuleRemoveRequest,
    authorization: str = Header(default=""),
) -> CodialRuleResponse:
    _check_auth(authorization)
    try:
        return CodialRuleResponse(rules=_get_rule_store(request).remove_rule(req.index))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="규칙 번호가 올바르지 않아요.") from exc


@router.post("/sessions/{session_id}/turns")
async def submit_turn(
    request: Request,
    session_id: str,
    req: SubmitTurnRequest,
    authorization: str = Header(default=""),
) -> dict[str, str]:
    _check_auth(authorization)

    worker_pool = request.app.state.turn_worker_pool
    if not isinstance(worker_pool, TurnWorkerPool):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="작업 워커를 사용할 수 없어요.")

    if req.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="세션 정보가 일치하지 않아요.")

    try:
        session_record = await _get_store(request).get_session(session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc

    if session_record.status == "ended":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="종료된 세션에는 요청할 수 없어요.")

    trace_id = str(uuid.uuid4())
    text = req.text or ""
    turn_id = await worker_pool.enqueue(
        session_id=session_id,
        user_id=req.user_id,
        text=text,
        attachments=req.attachments,
        provider=session_record.provider,
        model=session_record.model,
        mcp_enabled=session_record.mcp_enabled,
        mcp_profile_name=session_record.mcp_profile_name,
        subagent_name=session_record.subagent_name,
        trace_id=trace_id,
    )

    logger.info(
        "turn_received",
        trace_id=trace_id,
        session_id=session_id,
        turn_id=turn_id,
        user_id=req.user_id,
        has_text=bool(req.text),
        attachment_count=len(req.attachments),
    )
    return {"status": "accepted", "trace_id": trace_id, "turn_id": turn_id}


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(request: Request) -> dict[str, str]:
    worker_pool = getattr(request.app.state, "turn_worker_pool", None)
    if not isinstance(worker_pool, TurnWorkerPool):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="서비스가 아직 준비되지 않았어요.")
    return {"status": "ok"}
