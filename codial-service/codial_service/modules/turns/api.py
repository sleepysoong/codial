from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from codial_service.app.models import SubmitTurnRequest
from codial_service.app.store import SessionNotFoundError
from codial_service.modules.common.deps import get_turns_service, require_auth
from codial_service.modules.turns.service import SessionEndedError
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
        accepted = await get_turns_service(request).submit_turn(
            session_id=session_id,
            request=req,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없어요.") from exc
    except SessionEndedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    logger.info(
        "turn_received",
        trace_id=accepted.trace_id,
        session_id=session_id,
        turn_id=accepted.turn_id,
        user_id=req.user_id,
        channel_id=req.channel_id,
        idempotency_key=req.idempotency_key,
        has_text=accepted.has_text,
        attachment_count=accepted.attachment_count,
    )
    return {"status": "accepted", "trace_id": accepted.trace_id, "turn_id": accepted.turn_id}
