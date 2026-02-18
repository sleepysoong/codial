from __future__ import annotations

import asyncio
from typing import Any

import httpx

from libs.common.errors import AuthenticationError, RateLimitError, UpstreamTransientError


class DiscordApiClient:
    def __init__(self, bot_token: str, timeout_seconds: float) -> None:
        self._bot_token = bot_token
        self._timeout = timeout_seconds
        self._base_url = "https://discord.com/api/v10"

    async def create_guild_text_channel(
        self,
        guild_id: str,
        name: str,
        parent_id: str | None,
        permission_overwrites: list[dict[str, Any]],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "type": 0,
            "permission_overwrites": permission_overwrites,
        }
        if parent_id:
            body["parent_id"] = parent_id

        return await self._request(
            method="POST",
            path=f"/guilds/{guild_id}/channels",
            json=body,
            auth_required=True,
        )

    async def create_channel_message(self, channel_id: str, content: str) -> dict[str, Any]:
        return await self._request(
            method="POST",
            path=f"/channels/{channel_id}/messages",
            json={"content": content},
            auth_required=True,
        )

    async def create_followup_message(
        self,
        application_id: str,
        interaction_token: str,
        content: str,
        ephemeral: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"content": content}
        if ephemeral:
            payload["flags"] = 64

        return await self._request(
            method="POST",
            path=f"/webhooks/{application_id}/{interaction_token}",
            json=payload,
            auth_required=False,
        )

    async def _request(
        self,
        *,
        method: str,
        path: str,
        json: dict[str, Any],
        auth_required: bool,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if auth_required:
            if not self._bot_token:
                raise AuthenticationError("디스코드 봇 토큰이 없어요.")
            headers["Authorization"] = f"Bot {self._bot_token}"

        url = f"{self._base_url}{path}"

        max_attempts = 4
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(method=method, url=url, headers=headers, json=json)
            except httpx.TimeoutException as exc:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("디스코드 API 요청이 시간 초과됐어요.") from exc
                await asyncio.sleep(0.4 * (attempt + 1))
                continue
            except httpx.HTTPError as exc:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("디스코드 API 연결에 실패했어요.") from exc
                await asyncio.sleep(0.4 * (attempt + 1))
                continue

            if response.status_code == 429:
                retry_after = float(response.json().get("retry_after", 1.0))
                if attempt == max_attempts - 1:
                    raise RateLimitError("디스코드 API 제한 상태가 계속되고 있어요.")
                await asyncio.sleep(retry_after)
                continue

            if response.status_code in (401, 403):
                raise AuthenticationError("디스코드 API 인증 또는 권한에 실패했어요.")

            if response.status_code >= 500:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("디스코드 API 서버 오류가 발생했어요.")
                await asyncio.sleep(0.4 * (attempt + 1))
                continue

            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise UpstreamTransientError("디스코드 API 응답 형식이 올바르지 않아요.")
            return data

        raise UpstreamTransientError("디스코드 API 요청이 비정상 종료됐어요.")
