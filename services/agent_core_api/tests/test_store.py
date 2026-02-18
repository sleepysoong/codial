from __future__ import annotations

import pytest

from services.agent_core_api.app.store import InMemorySessionStore


@pytest.mark.asyncio
async def test_create_session_is_idempotent() -> None:
    local_store = InMemorySessionStore()
    first = await local_store.create_session("g1", "u1", "k1")
    second = await local_store.create_session("g1", "u1", "k1")
    assert first.session_id == second.session_id


@pytest.mark.asyncio
async def test_bind_channel_updates_record() -> None:
    local_store = InMemorySessionStore()
    record = await local_store.create_session("g1", "u1", "k2")
    updated = await local_store.bind_channel(record.session_id, "c-1")
    assert updated.channel_id == "c-1"


@pytest.mark.asyncio
async def test_end_session_updates_status() -> None:
    local_store = InMemorySessionStore()
    record = await local_store.create_session("g1", "u1", "k3")
    ended = await local_store.end_session(record.session_id)
    assert ended.status == "ended"


@pytest.mark.asyncio
async def test_set_provider_model_and_mcp() -> None:
    local_store = InMemorySessionStore()
    record = await local_store.create_session("g1", "u1", "k4")

    provider_updated = await local_store.set_provider(record.session_id, "openai-codex")
    assert provider_updated.provider == "openai-codex"

    model_updated = await local_store.set_model(record.session_id, "gpt-5")
    assert model_updated.model == "gpt-5"

    mcp_updated = await local_store.set_mcp(record.session_id, enabled=False, profile_name="safe")
    assert mcp_updated.mcp_enabled is False
    assert mcp_updated.mcp_profile_name == "safe"
