from __future__ import annotations

from dataclasses import dataclass

from codial_service.app.models import TurnAttachment


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


@dataclass(slots=True)
class ProviderResponse:
    output_text: str
    decision_summary: str


class ProviderAdapter:
    name: str

    async def generate(self, request: ProviderRequest) -> ProviderResponse:  # pragma: no cover - interface
        raise NotImplementedError
