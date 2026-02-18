from __future__ import annotations

import pytest
from codial_service.app.providers.base import ProviderRequest
from codial_service.app.providers.http_bridge_adapter import (
    HttpBridgeProviderAdapter,
    _parse_tool_requests,
)

from libs.common.errors import ConfigurationError


@pytest.mark.asyncio
async def test_http_bridge_adapter_requires_base_url() -> None:
    adapter = HttpBridgeProviderAdapter(
        name="github-copilot-sdk",
        base_url="",
        token="",
        timeout_seconds=5.0,
        provider_hint="GitHub Copilot SDK",
    )
    request = ProviderRequest(
        session_id="s1",
        user_id="u1",
        provider="github-copilot-sdk",
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


def test_parse_tool_requests_accepts_tool_requests_shape() -> None:
    body = {
        "tool_requests": [
            {
                "id": "call-1",
                "name": "read_file",
                "arguments": {"path": "README.md"},
            }
        ]
    }
    requests = _parse_tool_requests(body)
    assert len(requests) == 1
    assert requests[0].name == "read_file"
    assert requests[0].call_id == "call-1"
    assert requests[0].arguments == {"path": "README.md"}
