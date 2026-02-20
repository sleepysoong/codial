from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from codial_service.app.models import (
    BindChannelRequest,
    BindChannelResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionResponse,
    SessionConfigResponse,
    SetMcpRequest,
    SetModelRequest,
    SetProviderRequest,
    SetSubagentRequest,
)
from codial_service.app.store import SessionNotFoundError, SessionRecord
from codial_service.modules.common.deps import get_session_service, require_auth
from codial_service.modules.sessions.service import ProviderNotEnabledError, SubagentNotFoundError
from libs.common.logging import get_logger

router = APIRouter()
logger = get_logger("codial_service.modules.sessions")


def _to_session_config_response(record: SessionRecord) -> SessionConfigResponse:
    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
        subagent_name=record.subagent_name,
    )


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: Request,
    req: CreateSessionRequest,
    authorization: str = Header(default=""),
) -> CreateSessionResponse:
    require_auth(request, authorization)
    record = await get_session_service(request).create_session(
        req.guild_id,
        req.requester_id,
        req.idempotency_key,
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
    require_auth(request, authorization)
    try:
        record = await get_session_service(request).bind_channel(session_id=session_id, channel_id=req.channel_id)
    except SessionNotFoundError as exc:
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
    require_auth(request, authorization)
    try:
        record = await get_session_service(request).end_session(session_id=session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return EndSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/provider", response_model=SessionConfigResponse)
async def set_provider(
    request: Request,
    session_id: str,
    req: SetProviderRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    require_auth(request, authorization)

    try:
        record = await get_session_service(request).set_provider(session_id=session_id, provider=req.provider)
    except ProviderNotEnabledError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return _to_session_config_response(record)


@router.post("/sessions/{session_id}/model", response_model=SessionConfigResponse)
async def set_model(
    request: Request,
    session_id: str,
    req: SetModelRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    require_auth(request, authorization)
    try:
        record = await get_session_service(request).set_model(session_id=session_id, model=req.model)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return _to_session_config_response(record)


@router.post("/sessions/{session_id}/mcp", response_model=SessionConfigResponse)
async def set_mcp(
    request: Request,
    session_id: str,
    req: SetMcpRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    require_auth(request, authorization)
    try:
        record = await get_session_service(request).set_mcp(
            session_id=session_id,
            enabled=req.enabled,
            profile_name=req.profile_name,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    return _to_session_config_response(record)


@router.post("/sessions/{session_id}/subagent", response_model=SessionConfigResponse)
async def set_subagent(
    request: Request,
    session_id: str,
    req: SetSubagentRequest,
    authorization: str = Header(default=""),
) -> SessionConfigResponse:
    require_auth(request, authorization)

    try:
        record = await get_session_service(request).set_subagent(
            session_id=session_id,
            name=req.name,
        )
    except SubagentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc

    return _to_session_config_response(record)
