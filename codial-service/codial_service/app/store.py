from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from enum import Enum

from libs.common.errors import NotFoundError


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"


class SessionNotFoundError(NotFoundError):
    """요청한 세션을 찾을 수 없어요."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"세션을 찾을 수 없어요: {session_id!r}")
        self.session_id = session_id


@dataclass(slots=True, frozen=True)
class SessionRecord:
    session_id: str
    guild_id: str
    requester_id: str
    channel_id: str | None
    status: SessionStatus
    provider: str
    model: str
    mcp_enabled: bool
    mcp_profile_name: str | None
    subagent_name: str | None

    def with_channel(self, channel_id: str) -> "SessionRecord":
        return SessionRecord(
            session_id=self.session_id,
            guild_id=self.guild_id,
            requester_id=self.requester_id,
            channel_id=channel_id,
            status=self.status,
            provider=self.provider,
            model=self.model,
            mcp_enabled=self.mcp_enabled,
            mcp_profile_name=self.mcp_profile_name,
            subagent_name=self.subagent_name,
        )

    def with_status(self, status: SessionStatus) -> "SessionRecord":
        return SessionRecord(
            session_id=self.session_id,
            guild_id=self.guild_id,
            requester_id=self.requester_id,
            channel_id=self.channel_id,
            status=status,
            provider=self.provider,
            model=self.model,
            mcp_enabled=self.mcp_enabled,
            mcp_profile_name=self.mcp_profile_name,
            subagent_name=self.subagent_name,
        )

    def with_provider(self, provider: str) -> "SessionRecord":
        return SessionRecord(
            session_id=self.session_id,
            guild_id=self.guild_id,
            requester_id=self.requester_id,
            channel_id=self.channel_id,
            status=self.status,
            provider=provider,
            model=self.model,
            mcp_enabled=self.mcp_enabled,
            mcp_profile_name=self.mcp_profile_name,
            subagent_name=self.subagent_name,
        )

    def with_model(self, model: str) -> "SessionRecord":
        return SessionRecord(
            session_id=self.session_id,
            guild_id=self.guild_id,
            requester_id=self.requester_id,
            channel_id=self.channel_id,
            status=self.status,
            provider=self.provider,
            model=model,
            mcp_enabled=self.mcp_enabled,
            mcp_profile_name=self.mcp_profile_name,
            subagent_name=self.subagent_name,
        )

    def with_mcp(self, enabled: bool, profile_name: str | None) -> "SessionRecord":
        return SessionRecord(
            session_id=self.session_id,
            guild_id=self.guild_id,
            requester_id=self.requester_id,
            channel_id=self.channel_id,
            status=self.status,
            provider=self.provider,
            model=self.model,
            mcp_enabled=enabled,
            mcp_profile_name=profile_name,
            subagent_name=self.subagent_name,
        )

    def with_subagent(self, subagent_name: str | None) -> "SessionRecord":
        return SessionRecord(
            session_id=self.session_id,
            guild_id=self.guild_id,
            requester_id=self.requester_id,
            channel_id=self.channel_id,
            status=self.status,
            provider=self.provider,
            model=self.model,
            mcp_enabled=self.mcp_enabled,
            mcp_profile_name=self.mcp_profile_name,
            subagent_name=subagent_name,
        )


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
                status=SessionStatus.ACTIVE,
                provider=default_provider,
                model=default_model,
                mcp_enabled=default_mcp_enabled,
                mcp_profile_name=default_mcp_profile_name,
                subagent_name=None,
            )
            self._sessions[session_id] = record
            self._by_idempotency[idempotency_key] = session_id
            return record

    def _require(self, session_id: str) -> SessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise SessionNotFoundError(session_id)
        return record

    async def bind_channel(self, session_id: str, channel_id: str) -> SessionRecord:
        async with self._lock:
            record = self._require(session_id).with_channel(channel_id)
            self._sessions[session_id] = record
            return record

    async def end_session(self, session_id: str) -> SessionRecord:
        async with self._lock:
            record = self._require(session_id).with_status(SessionStatus.ENDED)
            self._sessions[session_id] = record
            return record

    async def get_session(self, session_id: str) -> SessionRecord:
        async with self._lock:
            return self._require(session_id)

    async def set_provider(self, session_id: str, provider: str) -> SessionRecord:
        async with self._lock:
            record = self._require(session_id).with_provider(provider)
            self._sessions[session_id] = record
            return record

    async def set_model(self, session_id: str, model: str) -> SessionRecord:
        async with self._lock:
            record = self._require(session_id).with_model(model)
            self._sessions[session_id] = record
            return record

    async def set_mcp(self, session_id: str, enabled: bool, profile_name: str | None) -> SessionRecord:
        async with self._lock:
            record = self._require(session_id).with_mcp(enabled, profile_name)
            self._sessions[session_id] = record
            return record

    async def set_subagent(self, session_id: str, subagent_name: str | None) -> SessionRecord:
        async with self._lock:
            record = self._require(session_id).with_subagent(subagent_name)
            self._sessions[session_id] = record
            return record
