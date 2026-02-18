from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from libs.common.errors import UpstreamTransientError


class CoreApiClient:
    def __init__(self, base_url: str, token: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds

    async def create_session(self, guild_id: str, requester_id: str, idempotency_key: str) -> dict[str, Any]:
        payload: dict[str, str] = {
            "guild_id": guild_id,
            "requester_id": requester_id,
            "idempotency_key": idempotency_key,
        }
        return await self._request_json("POST", "/v1/sessions", payload)

    async def bind_channel(self, session_id: str, channel_id: str) -> dict[str, Any]:
        payload: dict[str, str] = {"channel_id": channel_id}
        return await self._request_json("POST", f"/v1/sessions/{session_id}/bind-channel", payload)

    async def submit_turn(
        self,
        session_id: str,
        user_id: str,
        channel_id: str,
        text: str,
        attachments: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        payload: dict[str, str | bool | None | list[dict[str, Any]]] = {
            "session_id": session_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "text": text,
            "attachments": attachments,
            "idempotency_key": idempotency_key,
        }
        return await self._request_json("POST", f"/v1/sessions/{session_id}/turns", payload)

    async def end_session(self, session_id: str) -> dict[str, Any]:
        payload: dict[str, str] = {}
        return await self._request_json("POST", f"/v1/sessions/{session_id}/end", payload)

    async def set_provider(self, session_id: str, provider: str) -> dict[str, Any]:
        payload: dict[str, str] = {"provider": provider}
        return await self._request_json("POST", f"/v1/sessions/{session_id}/provider", payload)

    async def set_model(self, session_id: str, model: str) -> dict[str, Any]:
        payload: dict[str, str] = {"model": model}
        return await self._request_json("POST", f"/v1/sessions/{session_id}/model", payload)

    async def set_mcp(
        self,
        session_id: str,
        enabled: bool,
        profile_name: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, str | bool | None] = {
            "enabled": enabled,
            "profile_name": profile_name,
        }
        return await self._request_json("POST", f"/v1/sessions/{session_id}/mcp", payload)

    async def set_subagent(self, session_id: str, name: str | None) -> dict[str, Any]:
        payload: dict[str, str | None] = {"name": name}
        return await self._request_json("POST", f"/v1/sessions/{session_id}/subagent", payload)

    async def get_codial_rules(self) -> dict[str, Any]:
        return await self._request_json("GET", "/v1/codial/rules")

    async def add_codial_rule(self, rule: str) -> dict[str, Any]:
        payload: dict[str, str] = {"rule": rule}
        return await self._request_json("POST", "/v1/codial/rules", payload)

    async def remove_codial_rule(self, index: int) -> dict[str, Any]:
        payload: dict[str, int] = {"index": index}
        return await self._request_json("DELETE", "/v1/codial/rules", payload)

    async def _request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, str | bool | int | None | list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                request_kwargs: dict[str, Any] = {
                    "method": method,
                    "url": f"{self._base_url}{path}",
                    "headers": headers,
                }
                if method.upper() != "GET":
                    request_kwargs["json"] = payload or {}
                response = await client.request(**request_kwargs)
        except httpx.TimeoutException as exc:
            raise UpstreamTransientError("코어 API 요청이 시간 초과됐어요.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamTransientError("코어 API 연결에 실패했어요.") from exc

        if response.status_code >= 500:
            raise UpstreamTransientError("코어 API 서버 오류가 발생했어요.")

        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise UpstreamTransientError("코어 API 응답 형식이 올바르지 않아요.")
        return data
