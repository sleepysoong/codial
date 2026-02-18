from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from codial_service.app.mcp_client import McpClient

from libs.common.errors import ConfigurationError


@pytest.mark.asyncio
async def test_mcp_client_requires_server_url() -> None:
    client = McpClient(server_url="", token="", timeout_seconds=3.0)
    with pytest.raises(ConfigurationError):
        await client.initialize(client_name="codial", client_version="0.1.0")


@dataclass(slots=True)
class _ExpectedCall:
    method: str
    result: dict[str, Any]


class _StubMcpClient(McpClient):
    def __init__(self, expected_calls: list[_ExpectedCall]) -> None:
        super().__init__(server_url="http://mcp.test", token="", timeout_seconds=3.0)
        self._expected_calls = expected_calls
        self.notifications: list[str] = []

    async def _notify(self, method: str) -> None:
        self.notifications.append(method)

    async def _call(
        self,
        method: str,
        params: dict[str, Any],
        *,
        include_protocol_header: bool = True,
        include_session_header: bool = True,
    ) -> dict[str, Any]:
        del params, include_protocol_header, include_session_header
        if not self._expected_calls:
            raise AssertionError("예상보다 많은 MCP 호출이 발생했어요.")
        next_call = self._expected_calls.pop(0)
        assert next_call.method == method
        return next_call.result


@pytest.mark.asyncio
async def test_mcp_initialize_sends_initialized_notification() -> None:
    client = _StubMcpClient(
        expected_calls=[
            _ExpectedCall(
                method="initialize",
                result={
                    "result": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "test-server", "version": "1.2.3"},
                        "instructions": "테스트 서버예요.",
                    }
                },
            )
        ]
    )

    initialized = await client.initialize(client_name="codial", client_version="0.1.0")
    assert initialized.server_name == "test-server"
    assert initialized.server_version == "1.2.3"
    assert initialized.protocol_version == "2025-11-25"
    assert initialized.server_capabilities == {"tools": {}}
    assert initialized.instructions == "테스트 서버예요."
    assert client.notifications == ["notifications/initialized"]


@pytest.mark.asyncio
async def test_mcp_list_methods_follow_pagination() -> None:
    client = _StubMcpClient(
        expected_calls=[
            _ExpectedCall(
                method="tools/list",
                result={
                    "result": {
                        "tools": [
                            {
                                "name": "search_docs",
                                "title": "문서 검색",
                                "description": "문서를 검색해요.",
                                "inputSchema": {"type": "object"},
                            }
                        ],
                        "nextCursor": "next-1",
                    }
                },
            ),
            _ExpectedCall(
                method="tools/list",
                result={
                    "result": {
                        "tools": [
                            {
                                "name": "open_file",
                                "description": "파일을 열어요.",
                                "inputSchema": {"type": "object"},
                            }
                        ]
                    }
                },
            ),
            _ExpectedCall(
                method="prompts/list",
                result={
                    "result": {
                        "prompts": [
                            {
                                "name": "code_review",
                                "description": "코드 리뷰 프롬프트예요.",
                                "arguments": [{"name": "code", "required": True}],
                            }
                        ]
                    }
                },
            ),
            _ExpectedCall(
                method="resources/list",
                result={
                    "result": {
                        "resources": [
                            {
                                "uri": "file:///workspace/README.md",
                                "name": "README.md",
                                "mimeType": "text/markdown",
                            }
                        ]
                    }
                },
            ),
            _ExpectedCall(
                method="resources/templates/list",
                result={
                    "result": {
                        "resourceTemplates": [
                            {
                                "uriTemplate": "file:///{path}",
                                "name": "project-files",
                            }
                        ]
                    }
                },
            ),
        ]
    )

    tools = await client.list_tools()
    prompts = await client.list_prompts()
    resources = await client.list_resources()
    templates = await client.list_resource_templates()

    assert [tool.name for tool in tools] == ["search_docs", "open_file"]
    assert prompts[0].name == "code_review"
    assert prompts[0].arguments[0].name == "code"
    assert resources[0].uri == "file:///workspace/README.md"
    assert templates[0].uri_template == "file:///{path}"
