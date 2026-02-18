from __future__ import annotations

import pytest

from libs.common.errors import ConfigurationError
from services.agent_core_api.app.providers.base import ProviderRequest
from services.agent_core_api.app.providers.http_bridge_adapter import HttpBridgeProviderAdapter


@pytest.mark.asyncio
async def test_http_bridge_adapter_requires_base_url() -> None:
    adapter = HttpBridgeProviderAdapter(
        name="openai-codex",
        base_url="",
        token="",
        timeout_seconds=5.0,
        provider_hint="Codex",
    )
    request = ProviderRequest(
        session_id="s1",
        user_id="u1",
        provider="openai-codex",
        model="gpt-5",
        text="테스트",
        attachments=[],
        mcp_enabled=True,
        mcp_profile_name="default",
        rules_summary="rules",
        agents_summary="agents",
        skills_summary="skills",
        claude_memory_summary="memory",
    )
    with pytest.raises(ConfigurationError):
        await adapter.generate(request)
