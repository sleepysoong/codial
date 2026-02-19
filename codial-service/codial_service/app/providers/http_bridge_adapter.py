from __future__ import annotations

from typing import Any

import httpx

from codial_service.app.providers.base import (
    ProviderAdapter,
    ProviderRequest,
    ProviderResponse,
    ProviderToolRequest,
)
from libs.common.errors import ConfigurationError, UpstreamTransientError


class HttpBridgeProviderAdapter(ProviderAdapter):
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        token: str,
        timeout_seconds: float,
        provider_hint: str,
    ) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._provider_hint = provider_hint

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self._base_url:
            raise ConfigurationError(f"{self._provider_hint} 브리지 주소가 설정되지 않았어요.")

        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        payload: dict[str, Any] = {
            "session_id": request.session_id,
            "user_id": request.user_id,
            "provider": request.provider,
            "model": request.model,
            "text": request.text,
            "mcp_enabled": request.mcp_enabled,
            "mcp_profile_name": request.mcp_profile_name,
            "system_memory_summary": request.system_memory_summary,
            "tool_call_round": request.tool_call_round,
            "mcp_tools": [
                {
                    "name": tool.name,
                    "title": tool.title,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "output_schema": tool.output_schema,
                }
                for tool in request.tool_specs
            ],
            "tool_results": [
                {
                    "name": result.name,
                    "call_id": result.call_id,
                    "ok": result.ok,
                    "result": result.result,
                    "error": result.error,
                }
                for result in request.tool_results
            ],
            "attachments": [
                {
                    "attachment_id": attachment.attachment_id,
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size": attachment.size,
                    "url": attachment.url,
                }
                for attachment in request.attachments
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/v1/generate",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise UpstreamTransientError(f"{self._provider_hint} 브리지 요청이 시간 초과됐어요.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamTransientError(f"{self._provider_hint} 브리지 연결에 실패했어요.") from exc

        if response.status_code >= 500:
            raise UpstreamTransientError(f"{self._provider_hint} 브리지 서버 오류가 발생했어요.")

        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise UpstreamTransientError(f"{self._provider_hint} 브리지 응답 형식이 올바르지 않아요.")

        output_text_value = body.get("output_text")
        decision_summary_value = body.get("decision_summary")
        output_text = output_text_value if isinstance(output_text_value, str) else ""
        tool_requests = _parse_tool_requests(body)
        decision_summary = (
            decision_summary_value
            if isinstance(decision_summary_value, str)
            else (
                f"{self._provider_hint} 응답을 받았어요."
                if not tool_requests
                else f"{self._provider_hint} 도구 호출을 요청했어요."
            )
        )
        return ProviderResponse(
            output_text=output_text,
            decision_summary=decision_summary,
            tool_requests=tool_requests,
        )


def _parse_tool_requests(body: dict[str, Any]) -> list[ProviderToolRequest]:
    raw_calls = body.get("tool_requests")
    if not isinstance(raw_calls, list):
        raw_calls = body.get("tool_calls")
    if not isinstance(raw_calls, list):
        return []

    requests: list[ProviderToolRequest] = []
    for item in raw_calls:
        if not isinstance(item, dict):
            continue

        name_value = item.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            continue

        arguments_value = item.get("arguments")
        arguments = arguments_value if isinstance(arguments_value, dict) else {}

        call_id_value = item.get("call_id")
        if not isinstance(call_id_value, str):
            raw_id_value = item.get("id")
            call_id_value = raw_id_value if isinstance(raw_id_value, str) else None

        requests.append(
            ProviderToolRequest(
                name=name_value.strip(),
                arguments=arguments,
                call_id=call_id_value,
            )
        )

    return requests
