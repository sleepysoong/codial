from __future__ import annotations

import pytest

from libs.common.errors import ConfigurationError
from services.agent_core_api.app.mcp_client import McpClient


@pytest.mark.asyncio
async def test_mcp_client_requires_server_url() -> None:
    client = McpClient(server_url="", token="", timeout_seconds=3.0)
    with pytest.raises(ConfigurationError):
        await client.initialize(client_name="codial", client_version="0.1.0")
