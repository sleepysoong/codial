from __future__ import annotations

from pathlib import Path

from codial_service.app.policy_loader import PolicyLoader, extract_agent_defaults
from codial_service.app.providers.catalog import choose_default_provider
from codial_service.app.store import InMemorySessionStore, SessionRecord
from codial_service.app.subagent_spec import default_subagent_search_paths, discover_subagents

_DEFAULT_MODEL = "gpt-5-mini"
_DEFAULT_MCP_ENABLED = True
_DEFAULT_MCP_PROFILE = "default"


class ProviderNotEnabledError(ValueError):
    """활성화되지 않은 프로바이더를 선택했어요."""


class SubagentNotFoundError(LookupError):
    """요청한 서브에이전트를 찾지 못했어요."""


class SessionService:
    """세션 관련 유스케이스를 모아요."""

    def __init__(
        self,
        *,
        store: InMemorySessionStore,
        policy_loader: PolicyLoader,
        enabled_provider_names: list[str],
        workspace_root: str,
    ) -> None:
        self._store = store
        self._policy_loader = policy_loader
        self._enabled_provider_names = list(enabled_provider_names)
        self._enabled_provider_name_set = set(enabled_provider_names)
        self._workspace_root = Path(workspace_root)

    async def create_session(
        self,
        guild_id: str,
        requester_id: str,
        idempotency_key: str,
    ) -> SessionRecord:
        policy_snapshot = self._policy_loader.load()
        agent_defaults = extract_agent_defaults(policy_snapshot.agents_text)

        default_provider = choose_default_provider(
            agent_defaults.provider,
            self._enabled_provider_names,
        )
        default_model = agent_defaults.model or _DEFAULT_MODEL
        default_mcp_enabled = (
            agent_defaults.mcp_enabled
            if agent_defaults.mcp_enabled is not None
            else _DEFAULT_MCP_ENABLED
        )
        default_mcp_profile_name = agent_defaults.mcp_profile_name or _DEFAULT_MCP_PROFILE

        return await self._store.create_session(
            guild_id,
            requester_id,
            idempotency_key,
            default_provider=default_provider,
            default_model=default_model,
            default_mcp_enabled=default_mcp_enabled,
            default_mcp_profile_name=default_mcp_profile_name,
        )

    async def bind_channel(self, *, session_id: str, channel_id: str) -> SessionRecord:
        return await self._store.bind_channel(session_id=session_id, channel_id=channel_id)

    async def end_session(self, *, session_id: str) -> SessionRecord:
        return await self._store.end_session(session_id=session_id)

    async def set_provider(self, *, session_id: str, provider: str) -> SessionRecord:
        if provider not in self._enabled_provider_name_set:
            enabled_text = ", ".join(sorted(self._enabled_provider_name_set))
            raise ProviderNotEnabledError(f"현재 사용할 수 없는 프로바이더예요. 사용 가능 목록: {enabled_text}")
        return await self._store.set_provider(session_id=session_id, provider=provider)

    async def set_model(self, *, session_id: str, model: str) -> SessionRecord:
        return await self._store.set_model(session_id=session_id, model=model)

    async def set_mcp(self, *, session_id: str, enabled: bool, profile_name: str | None) -> SessionRecord:
        return await self._store.set_mcp(
            session_id=session_id,
            enabled=enabled,
            profile_name=profile_name,
        )

    async def set_subagent(self, *, session_id: str, name: str | None) -> SessionRecord:
        normalized_name = self._normalize_subagent_name(name)
        if normalized_name is not None and normalized_name not in self._available_subagent_names():
            raise SubagentNotFoundError("서브에이전트를 찾을 수 없어요.")
        return await self._store.set_subagent(session_id=session_id, subagent_name=normalized_name)

    @staticmethod
    def _normalize_subagent_name(name: str | None) -> str | None:
        requested_name = name.strip() if isinstance(name, str) else ""
        return requested_name if requested_name else None

    def _available_subagent_names(self) -> set[str]:
        specs = discover_subagents(default_subagent_search_paths(self._workspace_root))
        return {spec.name for spec in specs}
