from __future__ import annotations

import asyncio
from typing import Any

import httpx

from codial_service.app.mcp_protocol import (
    JSONRPC_VERSION,
    MCP_PROTOCOL_VERSION,
    McpInitializeResult,
    McpPrompt,
    McpPromptArgument,
    McpResource,
    McpResourceTemplate,
    McpTool,
)
from libs.common.errors import ConfigurationError, UpstreamTransientError


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
        # Lock을 역할별로 분리해요 — _state_lock 하나로 묶으면 ensure_initialized 안에서
        # _call_raw가 _state_lock을 재획득하려다 데드락이 발생해요 (#2)
        self._request_id_lock = asyncio.Lock()   # request ID 카운터 전용
        self._init_lock = asyncio.Lock()          # 초기화 직렬화 전용
        self._session_id_lock = asyncio.Lock()    # session ID 갱신 전용
        self._request_id = 0
        self._protocol_version: str | None = None
        self._session_id: str | None = None
        # 초기화 결과를 캐싱해요 — 매 Turn마다 handshake를 반복하지 않아요 (#9)
        self._init_result: McpInitializeResult | None = None
        self._client = httpx.AsyncClient(timeout=self._timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ensure_initialized(self, *, client_name: str, client_version: str) -> McpInitializeResult:
        """최초 호출 시에만 handshake를 수행하고 이후엔 캐시를 반환해요.

        _init_lock 안에서 I/O를 수행하므로 _state_lock과 교차 획득이 없어요.
        이중 확인(double-checked locking) 패턴으로 불필요한 초기화를 막아요.
        """
        # Fast path: 이미 초기화됐으면 락 없이 즉시 반환해요.
        if self._init_result is not None:
            return self._init_result
        async with self._init_lock:
            # Slow path: 락 안에서 재확인해요.
            if self._init_result is not None:
                return self._init_result
            result = await self._do_initialize(client_name=client_name, client_version=client_version)
            self._init_result = result
            return result

    async def initialize(self, *, client_name: str, client_version: str) -> McpInitializeResult:
        """하위 호환성을 위해 남겨두되, 내부적으로 캐시를 사용해요."""
        return await self.ensure_initialized(client_name=client_name, client_version=client_version)

    async def _do_initialize(self, *, client_name: str, client_version: str) -> McpInitializeResult:
        params = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": client_name,
                "version": client_version,
            },
        }
        # _call을 통해 호출해요 — _call_raw를 직접 호출하면 테스트 스텁이 개입할 수 없어요.
        response = await self._call(
            "initialize",
            params,
            include_protocol_header=False,
            include_session_header=False,
        )
        result = response.get("result")
        if not isinstance(result, dict):
            raise UpstreamTransientError("MCP initialize 응답 형식이 올바르지 않아요.")

        protocol_version_value = result.get("protocolVersion")
        self._protocol_version = protocol_version_value if isinstance(protocol_version_value, str) else MCP_PROTOCOL_VERSION

        capabilities_value = result.get("capabilities")
        server_capabilities = capabilities_value if isinstance(capabilities_value, dict) else {}
        instructions_value = result.get("instructions")

        await self._notify("notifications/initialized")

        server_info = result.get("serverInfo")
        if not isinstance(server_info, dict):
            return McpInitializeResult(
                server_name=None,
                server_version=None,
                protocol_version=self._protocol_version,
                server_capabilities=server_capabilities,
                instructions=instructions_value if isinstance(instructions_value, str) else None,
                session_id=self._session_id,
            )

        name_value = server_info.get("name")
        version_value = server_info.get("version")
        return McpInitializeResult(
            server_name=name_value if isinstance(name_value, str) else None,
            server_version=version_value if isinstance(version_value, str) else None,
            protocol_version=self._protocol_version,
            server_capabilities=server_capabilities,
            instructions=instructions_value if isinstance(instructions_value, str) else None,
            session_id=self._session_id,
        )

    async def list_tools(self) -> list[McpTool]:
        tools_value = await self._list_paginated(method="tools/list", list_key="tools")
        tools: list[McpTool] = []
        for tool_item in tools_value:
            name_value = tool_item.get("name")
            if not isinstance(name_value, str):
                continue
            description_value = tool_item.get("description")
            title_value = tool_item.get("title")
            input_schema_value = tool_item.get("inputSchema")
            output_schema_value = tool_item.get("outputSchema")
            tools.append(
                McpTool(
                    name=name_value,
                    title=title_value if isinstance(title_value, str) else None,
                    description=description_value if isinstance(description_value, str) else None,
                    input_schema=input_schema_value if isinstance(input_schema_value, dict) else {},
                    output_schema=output_schema_value if isinstance(output_schema_value, dict) else None,
                )
            )
        return tools

    async def list_prompts(self) -> list[McpPrompt]:
        prompts_value = await self._list_paginated(method="prompts/list", list_key="prompts")
        prompts: list[McpPrompt] = []
        for prompt_item in prompts_value:
            name_value = prompt_item.get("name")
            if not isinstance(name_value, str):
                continue

            arguments: list[McpPromptArgument] = []
            arguments_value = prompt_item.get("arguments")
            if isinstance(arguments_value, list):
                for argument_item in arguments_value:
                    if not isinstance(argument_item, dict):
                        continue
                    argument_name = argument_item.get("name")
                    if not isinstance(argument_name, str):
                        continue
                    description_value = argument_item.get("description")
                    required_value = argument_item.get("required")
                    arguments.append(
                        McpPromptArgument(
                            name=argument_name,
                            description=description_value if isinstance(description_value, str) else None,
                            required=bool(required_value),
                        )
                    )

            title_value = prompt_item.get("title")
            description_value = prompt_item.get("description")
            prompts.append(
                McpPrompt(
                    name=name_value,
                    title=title_value if isinstance(title_value, str) else None,
                    description=description_value if isinstance(description_value, str) else None,
                    arguments=arguments,
                )
            )
        return prompts

    async def list_resources(self) -> list[McpResource]:
        resources_value = await self._list_paginated(method="resources/list", list_key="resources")
        resources: list[McpResource] = []
        for resource_item in resources_value:
            uri_value = resource_item.get("uri")
            name_value = resource_item.get("name")
            if not isinstance(uri_value, str) or not isinstance(name_value, str):
                continue
            title_value = resource_item.get("title")
            description_value = resource_item.get("description")
            mime_type_value = resource_item.get("mimeType")
            resources.append(
                McpResource(
                    uri=uri_value,
                    name=name_value,
                    title=title_value if isinstance(title_value, str) else None,
                    description=description_value if isinstance(description_value, str) else None,
                    mime_type=mime_type_value if isinstance(mime_type_value, str) else None,
                )
            )
        return resources

    async def list_resource_templates(self) -> list[McpResourceTemplate]:
        templates_value = await self._list_paginated(
            method="resources/templates/list",
            list_key="resourceTemplates",
        )
        templates: list[McpResourceTemplate] = []
        for template_item in templates_value:
            uri_template_value = template_item.get("uriTemplate")
            name_value = template_item.get("name")
            if not isinstance(uri_template_value, str) or not isinstance(name_value, str):
                continue
            title_value = template_item.get("title")
            description_value = template_item.get("description")
            mime_type_value = template_item.get("mimeType")
            templates.append(
                McpResourceTemplate(
                    uri_template=uri_template_value,
                    name=name_value,
                    title=title_value if isinstance(title_value, str) else None,
                    description=description_value if isinstance(description_value, str) else None,
                    mime_type=mime_type_value if isinstance(mime_type_value, str) else None,
                )
            )
        return templates

    async def ping(self) -> None:
        response = await self._call("ping", {})
        result = response.get("result")
        if not isinstance(result, dict):
            raise UpstreamTransientError("MCP ping 응답 형식이 올바르지 않아요.")

    async def call_tool(self, *, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = await self._call("tools/call", {"name": name, "arguments": arguments})
        result = response.get("result")
        if not isinstance(result, dict):
            raise UpstreamTransientError("MCP tools/call 응답 형식이 올바르지 않아요.")
        return result

    async def _list_paginated(self, *, method: str, list_key: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()

        while True:
            params = {"cursor": cursor} if cursor else {}
            response = await self._call(method, params)
            result = response.get("result")
            if not isinstance(result, dict):
                raise UpstreamTransientError(f"MCP {method} 응답 형식이 올바르지 않아요.")

            page_value = result.get(list_key)
            if isinstance(page_value, list):
                for item in page_value:
                    if isinstance(item, dict):
                        items.append(item)

            next_cursor_value = result.get("nextCursor")
            if not isinstance(next_cursor_value, str) or not next_cursor_value:
                break
            if next_cursor_value in seen_cursors:
                raise UpstreamTransientError("MCP pagination cursor 순환이 감지됐어요.")
            seen_cursors.add(next_cursor_value)
            cursor = next_cursor_value

        return items

    async def _notify(self, method: str) -> None:
        if not self._server_url:
            raise ConfigurationError("MCP 서버 주소가 설정되지 않았어요.")

        payload: dict[str, Any] = {
            "jsonrpc": JSONRPC_VERSION,
            "method": method,
        }
        headers = self._build_headers(include_accept_header=False)

        try:
            response = await self._client.post(self._server_url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise UpstreamTransientError("MCP 알림 전송이 시간 초과됐어요.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamTransientError("MCP 알림 전송 중 네트워크 오류가 발생했어요.") from exc

        if response.status_code >= 500:
            raise UpstreamTransientError("MCP 서버 오류가 발생했어요.")
        response.raise_for_status()

        if not response.content:
            return

        data = response.json()
        if not isinstance(data, dict):
            return
        error_value = data.get("error")
        if isinstance(error_value, dict):
            message_value = error_value.get("message")
            message = message_value if isinstance(message_value, str) else "MCP 오류가 발생했어요."
            raise UpstreamTransientError(message)

    def _build_headers(self, *, include_accept_header: bool) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if include_accept_header:
            headers["Accept"] = "application/json, text/event-stream"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self._protocol_version:
            headers["MCP-Protocol-Version"] = self._protocol_version
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id
        return headers

    async def _next_request_id(self) -> int:
        async with self._request_id_lock:
            self._request_id += 1
            return self._request_id

    async def _call(
        self,
        method: str,
        params: dict[str, Any],
        *,
        include_protocol_header: bool = True,
        include_session_header: bool = True,
    ) -> dict[str, Any]:
        return await self._call_raw(
            method,
            params,
            include_protocol_header=include_protocol_header,
            include_session_header=include_session_header,
        )

    async def _call_raw(
        self,
        method: str,
        params: dict[str, Any],
        *,
        include_protocol_header: bool = True,
        include_session_header: bool = True,
    ) -> dict[str, Any]:
        if not self._server_url:
            raise ConfigurationError("MCP 서버 주소가 설정되지 않았어요.")

        request_id = await self._next_request_id()
        payload = {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": method,
            "params": params,
        }
        headers = self._build_headers(include_accept_header=True)
        if not include_protocol_header:
            headers.pop("MCP-Protocol-Version", None)
        if not include_session_header:
            headers.pop("MCP-Session-Id", None)

        try:
            response = await self._client.post(self._server_url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise UpstreamTransientError("MCP 요청이 시간 초과됐어요.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamTransientError("MCP 요청 중 네트워크 오류가 발생했어요.") from exc

        if response.status_code >= 500:
            raise UpstreamTransientError("MCP 서버 오류가 발생했어요.")
        response.raise_for_status()

        async with self._session_id_lock:
            session_id_value = response.headers.get("MCP-Session-Id")
            if isinstance(session_id_value, str) and session_id_value:
                self._session_id = session_id_value

        data = response.json()
        if not isinstance(data, dict):
            raise UpstreamTransientError("MCP 응답 형식이 올바르지 않아요.")

        error_value = data.get("error")
        if isinstance(error_value, dict):
            message_value = error_value.get("message")
            message = message_value if isinstance(message_value, str) else "MCP 오류가 발생했어요."
            raise UpstreamTransientError(message)

        return data
