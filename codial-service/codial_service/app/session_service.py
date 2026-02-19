"""세션 생성에 관한 비즈니스 로직을 캡슐화해요.

routes.py는 HTTP 관심사(인증, 요청 파싱, 응답 직렬화, 오류 매핑)만 다루고,
세션 생성의 도메인 규칙(정책 기반 기본값 결정)은 이 서비스에서 처리해요. (#7)
"""
from __future__ import annotations

from codial_service.app.policy_loader import PolicyLoader, extract_agent_defaults
from codial_service.app.providers.catalog import choose_default_provider
from codial_service.app.store import InMemorySessionStore, SessionRecord
from libs.common.logging import get_logger

logger = get_logger("codial_service.session_service")

_DEFAULT_MODEL = "gpt-5-mini"
_DEFAULT_MCP_ENABLED = True
_DEFAULT_MCP_PROFILE = "default"


class SessionService:
    """세션 생성 도메인 로직을 담당해요."""

    def __init__(
        self,
        store: InMemorySessionStore,
        policy_loader: PolicyLoader,
        enabled_provider_names: list[str],
    ) -> None:
        self._store = store
        self._policy_loader = policy_loader
        self._enabled_provider_names = enabled_provider_names

    async def create_session(
        self,
        guild_id: str,
        requester_id: str,
        idempotency_key: str | None,
    ) -> SessionRecord:
        """정책에서 에이전트 기본값을 읽어 세션을 생성해요.

        1. 현재 정책 스냅샷을 로드해요.
        2. AGENTS 섹션에서 기본 프로바이더·모델·MCP 설정을 추출해요.
        3. 활성화된 프로바이더 목록과 대조해 실제 기본 프로바이더를 결정해요.
        4. 결정된 기본값으로 세션을 생성해요.
        """
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
