from __future__ import annotations

import uuid
from dataclasses import dataclass

from codial_service.app.models import SubmitTurnRequest
from codial_service.app.store import InMemorySessionStore, SessionStatus
from codial_service.modules.turns.worker import TurnWorkerPool


class SessionEndedError(RuntimeError):
    """종료된 세션에 턴 제출을 시도했어요."""


@dataclass(slots=True)
class TurnAccepted:
    trace_id: str
    turn_id: str
    has_text: bool
    attachment_count: int


class TurnsService:
    """턴 제출 유스케이스를 담당해요."""

    def __init__(self, *, store: InMemorySessionStore, worker_pool: TurnWorkerPool) -> None:
        self._store = store
        self._worker_pool = worker_pool

    async def submit_turn(self, *, session_id: str, request: SubmitTurnRequest) -> TurnAccepted:
        session_record = await self._store.get_session(session_id=session_id)
        if session_record.status == SessionStatus.ENDED:
            raise SessionEndedError("종료된 세션에는 요청할 수 없어요.")

        trace_id = str(uuid.uuid4())
        text = request.text or ""
        turn_id = await self._worker_pool.enqueue(
            session_id=session_id,
            user_id=request.user_id,
            text=text,
            attachments=request.attachments,
            provider=session_record.provider,
            model=session_record.model,
            mcp_enabled=session_record.mcp_enabled,
            mcp_profile_name=session_record.mcp_profile_name,
            subagent_name=session_record.subagent_name,
            trace_id=trace_id,
        )
        return TurnAccepted(
            trace_id=trace_id,
            turn_id=turn_id,
            has_text=bool(request.text),
            attachment_count=len(request.attachments),
        )
