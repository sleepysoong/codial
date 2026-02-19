from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status

from codial_service.app.models import SubmitTurnRequest
from codial_service.app.store import SessionNotFoundError, SessionStatus
from codial_service.modules.common.deps import get_store, get_worker_pool, require_auth
from libs.common.logging import get_logger

router = APIRouter()
logger = get_logger("codial_service.modules.turns")


@router.post("/sessions/{session_id}/turns")
async def submit_turn(
    request: Request,
    session_id: str,
    req: SubmitTurnRequest,
    authorization: str = Header(default=""),
) -> dict[str, str]:
    require_auth(request, authorization)

    try:
        session_record = await get_store(request).get_session(session_id=session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc

    if session_record.status == SessionStatus.ENDED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="종료된 세션에는 요청할 수 없어요.")

    trace_id = str(uuid.uuid4())
    text = req.text or ""
    turn_id = await get_worker_pool(request).enqueue(
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
        channel_id=req.channel_id,
        idempotency_key=req.idempotency_key,
        has_text=bool(req.text),
        attachment_count=len(req.attachments),
    )
    return {"status": "accepted", "trace_id": trace_id, "turn_id": turn_id}
