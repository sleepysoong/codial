from __future__ import annotations

from typing import Any

import httpx

from libs.common.errors import ConfigurationError, UpstreamTransientError
from services.agent_core_api.app.mcp_protocol import JSONRPC_VERSION, McpInitializeResult, McpTool


class McpClient:
    def __init__(
        self,
        *,
        server_url: str,
        token: str,
        timeout_seconds: float,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._request_id = 0

    async def initialize(self, *, client_name: str, client_version: str) -> McpInitializeResult:
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": client_name,
                "version": client_version,
            },
        }
        response = await self._call("initialize", params)
        result = response.get("result")
        if not isinstance(result, dict):
            raise UpstreamTransientError("MCP initialize 응답 형식이 올바르지 않아요.")

        server_info = result.get("serverInfo")
        if not isinstance(server_info, dict):
            return McpInitializeResult(server_name=None, server_version=None)

        name_value = server_info.get("name")
        version_value = server_info.get("version")
        return McpInitializeResult(
            server_name=name_value if isinstance(name_value, str) else None,
            server_version=version_value if isinstance(version_value, str) else None,
        )

    async def list_tools(self) -> list[McpTool]:
        response = await self._call("tools/list", {})
        result = response.get("result")
        if not isinstance(result, dict):
            raise UpstreamTransientError("MCP tools/list 응답 형식이 올바르지 않아요.")

        tools_value = result.get("tools")
        if not isinstance(tools_value, list):
            return []

        tools: list[McpTool] = []
        for tool_item in tools_value:
            if not isinstance(tool_item, dict):
                continue
            name_value = tool_item.get("name")
            if not isinstance(name_value, str):
                continue
            description_value = tool_item.get("description")
            input_schema_value = tool_item.get("inputSchema")
            tools.append(
                McpTool(
                    name=name_value,
                    description=description_value if isinstance(description_value, str) else None,
                    input_schema=input_schema_value if isinstance(input_schema_value, dict) else {},
                )
            )
        return tools

    async def call_tool(self, *, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = await self._call("tools/call", {"name": name, "arguments": arguments})
        result = response.get("result")
        if not isinstance(result, dict):
            raise UpstreamTransientError("MCP tools/call 응답 형식이 올바르지 않아요.")
        return result

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._server_url:
            raise ConfigurationError("MCP 서버 주소가 설정되지 않았어요.")

        self._request_id += 1
        payload = {
            "jsonrpc": JSONRPC_VERSION,
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(self._server_url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise UpstreamTransientError("MCP 요청이 시간 초과됐어요.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamTransientError("MCP 요청 중 네트워크 오류가 발생했어요.") from exc

        if response.status_code >= 500:
            raise UpstreamTransientError("MCP 서버 오류가 발생했어요.")
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, dict):
            raise UpstreamTransientError("MCP 응답 형식이 올바르지 않아요.")

        error_value = data.get("error")
        if isinstance(error_value, dict):
            message_value = error_value.get("message")
            message = message_value if isinstance(message_value, str) else "MCP 오류가 발생했어요."
            raise UpstreamTransientError(message)

        return data
