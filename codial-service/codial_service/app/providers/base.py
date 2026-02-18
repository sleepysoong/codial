from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codial_service.app.models import TurnAttachment


@dataclass(slots=True)
class ProviderToolSpec:
    name: str
    title: str | None
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None


@dataclass(slots=True)
class ProviderToolRequest:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass(slots=True)
class ProviderToolResult:
    name: str
    ok: bool
    call_id: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass(slots=True)
class ProviderRequest:
    session_id: str
    user_id: str
    provider: str
    model: str
    text: str
    attachments: list[TurnAttachment]
    mcp_enabled: bool
    mcp_profile_name: str | None
    rules_summary: str
    agents_summary: str
    skills_summary: str
    claude_memory_summary: str
    mcp_tools: list[ProviderToolSpec] = field(default_factory=list)
    tool_results: list[ProviderToolResult] = field(default_factory=list)
    tool_call_round: int = 0


@dataclass(slots=True)
class ProviderResponse:
    output_text: str
    decision_summary: str
    tool_requests: list[ProviderToolRequest] = field(default_factory=list)


class ProviderAdapter:
    name: str

    async def generate(self, request: ProviderRequest) -> ProviderResponse:  # pragma: no cover - interface
        raise NotImplementedError
