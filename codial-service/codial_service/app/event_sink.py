from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from libs.common.errors import UpstreamTransientError


class GatewayEventSink:
    def __init__(self, base_url: str, token: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def publish(self, event: dict[str, Any]) -> None:
        max_attempts = 4
        headers = {"x-internal-token": self._token}
        for attempt in range(max_attempts):
            try:
                response = await self._client.post(
                    f"{self._base_url}/internal/stream-events",
                    json=event,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("게이트웨이 이벤트 전송이 시간 초과됐어요.") from exc
                await self._backoff(attempt)
                continue
            except httpx.HTTPError as exc:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("게이트웨이 이벤트 전송 네트워크 오류가 발생했어요.") from exc
                await self._backoff(attempt)
                continue

            if response.status_code >= 500:
                if attempt == max_attempts - 1:
                    raise UpstreamTransientError("게이트웨이 이벤트 수신 서버 오류가 발생했어요.")
                await self._backoff(attempt)
                continue

            response.raise_for_status()
            return

    @staticmethod
    async def _backoff(attempt: int) -> None:
        """지수 백오프에 ±20 % 범위의 full jitter를 적용해요."""
        base = 0.3 * (2 ** attempt)
        jitter = base * random.uniform(-0.2, 0.2)
        await asyncio.sleep(base + jitter)
