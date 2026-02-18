from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(slots=True)
class SessionBinding:
    session_id: str
    channel_id: str


class SessionBindingStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_channel_id: dict[str, SessionBinding] = {}
        self._by_session_id: dict[str, SessionBinding] = {}

    async def put(self, session_id: str, channel_id: str) -> None:
        async with self._lock:
            binding = SessionBinding(session_id=session_id, channel_id=channel_id)
            self._by_channel_id[channel_id] = binding
            self._by_session_id[session_id] = binding

    async def get_by_channel_id(self, channel_id: str) -> SessionBinding | None:
        async with self._lock:
            return self._by_channel_id.get(channel_id)

    async def get_by_session_id(self, session_id: str) -> SessionBinding | None:
        async with self._lock:
            return self._by_session_id.get(session_id)


store = SessionBindingStore()
