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
from codial_service.app.store import SessionNotFoundError
from codial_service.app.subagent_spec import default_subagent_search_paths, discover_subagents
from codial_service.modules.common.deps import (
    enabled_provider_names,
    get_settings,
    get_session_service,
    get_store,
    require_auth,
)
from libs.common.logging import get_logger

router = APIRouter()
logger = get_logger("codial_service.modules.sessions")


def _load_subagent_names(request: Request) -> set[str]:
    specs = discover_subagents(default_subagent_search_paths(get_settings(request).workspace_root))
    return {spec.name for spec in specs}


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
        record = await get_store(request).bind_channel(session_id=session_id, channel_id=req.channel_id)
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
        record = await get_store(request).end_session(session_id=session_id)
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

    enabled_providers = set(enabled_provider_names(request))
    if req.provider not in enabled_providers:
        enabled_text = ", ".join(sorted(enabled_providers))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 사용할 수 없는 프로바이더예요. 사용 가능 목록: {enabled_text}",
        )

    try:
        record = await get_store(request).set_provider(session_id=session_id, provider=req.provider)
    except SessionNotFoundError as exc:
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
    require_auth(request, authorization)
    try:
        record = await get_store(request).set_model(session_id=session_id, model=req.model)
    except SessionNotFoundError as exc:
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
    require_auth(request, authorization)
    try:
        record = await get_store(request).set_mcp(
            session_id=session_id,
            enabled=req.enabled,
            profile_name=req.profile_name,
        )
    except SessionNotFoundError as exc:
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
    require_auth(request, authorization)

    requested_name = req.name.strip() if isinstance(req.name, str) else ""
    normalized_name = requested_name if requested_name else None
    if normalized_name is not None:
        available_names = _load_subagent_names(request)
        if normalized_name not in available_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="서브에이전트를 찾을 수 없어요.",
            )

    try:
        record = await get_store(request).set_subagent(session_id=session_id, subagent_name=normalized_name)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc

    return SessionConfigResponse(
        session_id=record.session_id,
        provider=record.provider,
        model=record.model,
        mcp_enabled=record.mcp_enabled,
        mcp_profile_name=record.mcp_profile_name,
        subagent_name=record.subagent_name,
    )
