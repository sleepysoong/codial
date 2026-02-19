from __future__ import annotations

import pytest
from codial_service.app.store import InMemorySessionStore

from tests.conftest import create_test_session


@pytest.mark.asyncio
async def test_create_session_is_idempotent(session_store: InMemorySessionStore) -> None:
    first = await create_test_session(session_store, "k1")
    second = await create_test_session(session_store, "k1")
    assert first.session_id == second.session_id


@pytest.mark.asyncio
async def test_bind_channel_updates_record(session_store: InMemorySessionStore) -> None:
    record = await create_test_session(session_store, "k2")
    updated = await session_store.bind_channel(record.session_id, "c-1")
    assert updated.channel_id == "c-1"


@pytest.mark.asyncio
async def test_end_session_updates_status(session_store: InMemorySessionStore) -> None:
    record = await create_test_session(session_store, "k3")
    ended = await session_store.end_session(record.session_id)
    assert ended.status == "ended"


@pytest.mark.asyncio
async def test_set_provider_model_and_mcp(session_store: InMemorySessionStore) -> None:
    record = await create_test_session(session_store, "k4")

    provider_updated = await session_store.set_provider(record.session_id, "github-copilot-sdk")
    assert provider_updated.provider == "github-copilot-sdk"

    model_updated = await session_store.set_model(record.session_id, "gpt-5")
    assert model_updated.model == "gpt-5"

    mcp_updated = await session_store.set_mcp(record.session_id, enabled=False, profile_name="safe")
    assert mcp_updated.mcp_enabled is False
    assert mcp_updated.mcp_profile_name == "safe"

    subagent_updated = await session_store.set_subagent(record.session_id, subagent_name="planner")
    assert subagent_updated.subagent_name == "planner"

    subagent_cleared = await session_store.set_subagent(record.session_id, subagent_name=None)
    assert subagent_cleared.subagent_name is None
