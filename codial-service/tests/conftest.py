from __future__ import annotations

import pytest

from codial_service.app.store import InMemorySessionStore, SessionRecord


@pytest.fixture
def session_store() -> InMemorySessionStore:
    """각 테스트용으로 새로 생성한 빈 InMemorySessionStore예요."""
    return InMemorySessionStore()


async def create_test_session(store: InMemorySessionStore, idempotency_key: str = "k1") -> SessionRecord:
    """테스트용 세션을 기본값으로 생성하는 헬퍼예요."""
    return await store.create_session(
        "g1",
        "u1",
        idempotency_key,
        default_provider="github-copilot-sdk",
        default_model="gpt-5-mini",
        default_mcp_enabled=True,
        default_mcp_profile_name="default",
    )
