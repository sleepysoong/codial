from __future__ import annotations

import asyncio
from typing import Any

import httpx

from libs.common.errors import UpstreamTransientError


class GatewayEventSink:
    def __init__(self, base_url: str, token: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds

    async def publish(self, event: dict[str, Any]) -> None:
        max_attempts = 4
        headers = {"x-internal-token": self._token}
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        f"{self._base_url}/internal/stream-events",
                        json=event,
                        headers=headers,
                    )
            except httpx.TimeoutException as exc:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("게이트웨이 이벤트 전송이 시간 초과됐어요.") from exc
                await asyncio.sleep(0.3 * (attempt + 1))
                continue
            except httpx.HTTPError as exc:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("게이트웨이 이벤트 전송 네트워크 오류가 발생했어요.") from exc
                await asyncio.sleep(0.3 * (attempt + 1))
                continue

            if response.status_code >= 500:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("게이트웨이 이벤트 수신 서버 오류가 발생했어요.")
                await asyncio.sleep(0.3 * (attempt + 1))
                continue

            response.raise_for_status()
            return
