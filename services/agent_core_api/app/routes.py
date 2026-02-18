from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status

from libs.common.logging import get_logger
from services.agent_core_api.app.models import (
    BindChannelRequest,
    BindChannelResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionResponse,
    SessionConfigResponse,
    SetMcpRequest,
    SetModelRequest,
    SetProviderRequest,
    SubmitTurnRequest,
)
from services.agent_core_api.app.policy_loader import PolicyLoader, extract_agent_defaults
from services.agent_core_api.app.settings import settings
from services.agent_core_api.app.store import store
from services.agent_core_api.app.turn_worker import TurnWorkerPool

router = APIRouter(prefix="/v1")
logger = get_logger("agent_core_api.routes")


def _check_auth(authorization: str) -> None:
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했어요.")


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest, authorization: str = Header(default="")) -> CreateSessionResponse:
    _check_auth(authorization)

    policy_snapshot = PolicyLoader(workspace_root=settings.workspace_root).load()
    agent_defaults = extract_agent_defaults(policy_snapshot.agents_text)
    record = await store.create_session(
        req.guild_id,
        req.requester_id,
        req.idempotency_key,
        default_provider=agent_defaults.provider or "openai-api",
        default_model=agent_defaults.model or "gpt-5-mini",
        default_mcp_enabled=agent_defaults.mcp_enabled if agent_defaults.mcp_enabled is not None else True,
        default_mcp_profile_name=agent_defaults.mcp_profile_name or "default",
    )
    logger.info("session_created", session_id=record.session_id, guild_id=req.guild_id)
    return CreateSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/bind-channel", response_model=BindChannelResponse)
async def bind_channel(
    session_id: str,
    req: BindChannelRequest,
    authorization: str = Header(default=""),
) -> BindChannelResponse:
    _check_auth(authorization)
    try:
        record = await store.bind_channel(session_id=session_id, channel_id=req.channel_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc

    return BindChannelResponse(
        session_id=record.session_id,
        channel_id=req.channel_id,
        status=record.status,
    )


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_session(session_id: str, authorization: str = Header(default="")) -> EndSessionResponse:
    _check_auth(authorization)
    try:
        record = await store.end_session(session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return EndSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/provider", response_model=SessionConfigResponse)
async def set_provider(
    session_id: str,
    req: SetProviderRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    _check_auth(authorization)
    try:
        record = await store.set_provider(session_id=session_id, provider=req.provider)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
    )


@router.post("/sessions/{session_id}/model", response_model=SessionConfigResponse)
async def set_model(
    session_id: str,
    req: SetModelRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    _check_auth(authorization)
    try:
        record = await store.set_model(session_id=session_id, model=req.model)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
    )


@router.post("/sessions/{session_id}/mcp", response_model=SessionConfigResponse)
async def set_mcp(
    session_id: str,
    req: SetMcpRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    _check_auth(authorization)
    try:
        record = await store.set_mcp(
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
    )


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
        session_record = await store.get_session(session_id=session_id)
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
async def health_ready() -> dict[str, str]:
    return {"status": "ok"}
