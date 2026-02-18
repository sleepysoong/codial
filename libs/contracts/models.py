from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AttachmentInput(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    size: int = Field(ge=0)
    url: str


class TurnInput(BaseModel):
    session_id: str
    user_id: str
    channel_id: str
    text: str | None = None
    attachments: list[AttachmentInput] = Field(default_factory=list)
    idempotency_key: str


class StreamEvent(BaseModel):
    session_id: str
    turn_id: str
    type: Literal[
        "plan",
        "action",
        "tool_call",
        "tool_result_summary",
        "decision_summary",
        "response_delta",
        "final",
        "error",
    ]
    payload: dict[str, Any]
