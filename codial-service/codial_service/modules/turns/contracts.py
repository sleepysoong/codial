from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from codial_service.app.models import TurnAttachment


class EventSinkProtocol(Protocol):
    async def publish(self, event: dict[str, Any]) -> None: ...


class AttachmentIngestResultProtocol(Protocol):
    summary: str


class AttachmentIngestorProtocol(Protocol):
    async def ingest(
        self,
        *,
        session_id: str,
        turn_id: str,
        attachments: list[Any],
    ) -> AttachmentIngestResultProtocol: ...


class McpClientProtocol(Protocol):
    async def ensure_initialized(self, *, client_name: str, client_version: str) -> Any: ...
    async def list_tools(self) -> list[Any]: ...
    async def call_tool(self, *, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class TurnTask:
    turn_id: str
    trace_id: str
    session_id: str
    user_id: str
    text: str
    attachments: list[TurnAttachment]
    provider: str
    model: str
    mcp_enabled: bool
    mcp_profile_name: str | None
    subagent_name: str | None
