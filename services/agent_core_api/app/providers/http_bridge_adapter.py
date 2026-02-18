from __future__ import annotations

from typing import Any

import httpx

from libs.common.errors import ConfigurationError, UpstreamTransientError
from services.agent_core_api.app.providers.base import (
    ProviderAdapter,
    ProviderRequest,
    ProviderResponse,
)


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
            "claude_memory_summary": request.claude_memory_summary,
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
        output_text = output_text_value if isinstance(output_text_value, str) else "응답 본문이 비어 있어요."
        decision_summary = (
            decision_summary_value if isinstance(decision_summary_value, str) else f"{self._provider_hint} 응답을 받았어요."
        )
        return ProviderResponse(output_text=output_text, decision_summary=decision_summary)
