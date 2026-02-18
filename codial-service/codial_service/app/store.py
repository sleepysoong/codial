from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    guild_id: str
    requester_id: str
    channel_id: str | None
    status: str
    provider: str
    model: str
    mcp_enabled: bool
    mcp_profile_name: str | None
    subagent_name: str | None


class InMemorySessionStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, SessionRecord] = {}
        self._by_idempotency: dict[str, str] = {}

    async def create_session(
        self,
        guild_id: str,
        requester_id: str,
        idempotency_key: str,
        *,
        default_provider: str,
        default_model: str,
        default_mcp_enabled: bool,
        default_mcp_profile_name: str | None,
    ) -> SessionRecord:
        async with self._lock:
            existing_session_id = self._by_idempotency.get(idempotency_key)
            if existing_session_id is not None:
                return self._sessions[existing_session_id]

            session_id = str(uuid.uuid4())
            record = SessionRecord(
                session_id=session_id,
                guild_id=guild_id,
                requester_id=requester_id,
                channel_id=None,
                status="active",
                provider=default_provider,
                model=default_model,
                mcp_enabled=default_mcp_enabled,
                mcp_profile_name=default_mcp_profile_name,
                subagent_name=None,
            )
            self._sessions[session_id] = record
            self._by_idempotency[idempotency_key] = session_id
            return record

    async def bind_channel(self, session_id: str, channel_id: str) -> SessionRecord:
        async with self._lock:
            record = self._sessions[session_id]
            record.channel_id = channel_id
            return record

    async def end_session(self, session_id: str) -> SessionRecord:
        async with self._lock:
            record = self._sessions[session_id]
            record.status = "ended"
            return record

    async def get_session(self, session_id: str) -> SessionRecord:
        async with self._lock:
            return self._sessions[session_id]

    async def set_provider(self, session_id: str, provider: str) -> SessionRecord:
        async with self._lock:
            record = self._sessions[session_id]
            record.provider = provider
            return record

    async def set_model(self, session_id: str, model: str) -> SessionRecord:
        async with self._lock:
            record = self._sessions[session_id]
            record.model = model
            return record

    async def set_mcp(self, session_id: str, enabled: bool, profile_name: str | None) -> SessionRecord:
        async with self._lock:
            record = self._sessions[session_id]
            record.mcp_enabled = enabled
            record.mcp_profile_name = profile_name
            return record

    async def set_subagent(self, session_id: str, subagent_name: str | None) -> SessionRecord:
        async with self._lock:
            record = self._sessions[session_id]
            record.subagent_name = subagent_name
            return record


store = InMemorySessionStore()
