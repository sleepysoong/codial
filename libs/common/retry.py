from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable


async def retry_async(
    func: Callable[[], Awaitable[object]],
    *,
    retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    retry_filter: Callable[[Exception], bool],
) -> object:
    attempt = 0
    while True:
        try:
            return await func()
        except Exception as exc:
            if attempt >= retries or not retry_filter(exc):
                raise

            delay = min(base_delay_seconds * (2**attempt), max_delay_seconds)
            jitter = random.uniform(0, delay * 0.2)
            await asyncio.sleep(delay + jitter)
            attempt += 1
