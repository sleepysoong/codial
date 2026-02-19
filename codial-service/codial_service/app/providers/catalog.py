from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from codial_service.app.providers.base import ProviderAdapter
from codial_service.app.providers.http_bridge_adapter import HttpBridgeProviderAdapter
from libs.common.errors import ConfigurationError


class ProviderRuntimeSettings(Protocol):
    default_provider_name: str
    enabled_provider_names: list[str]  # #18 list[str]로 변경
    copilot_bridge_base_url: str
    copilot_bridge_token: str
    provider_bridge_timeout_seconds: float


# 프로바이더 팩토리 테이블이에요 — 새 프로바이더를 추가할 때 여기만 수정하면 돼요 (#8 OCP)
_ProviderFactory = Callable[["ProviderRuntimeSettings", str | None], ProviderAdapter]

_PROVIDER_FACTORIES: dict[str, _ProviderFactory] = {
    "github-copilot-sdk": lambda s, token_override: HttpBridgeProviderAdapter(
        name="github-copilot-sdk",
        base_url=s.copilot_bridge_base_url,
        token=token_override if token_override is not None else s.copilot_bridge_token,
        timeout_seconds=s.provider_bridge_timeout_seconds,
        provider_hint="GitHub Copilot SDK",
    ),
}

KNOWN_PROVIDER_NAMES: frozenset[str] = frozenset(_PROVIDER_FACTORIES.keys())


def get_enabled_provider_names(names: list[str], *, fallback_default: str) -> list[str]:
    resolved = names if names else [fallback_default]

    unknown = [p for p in resolved if p not in KNOWN_PROVIDER_NAMES]
    if unknown:
        unknown_text = ", ".join(sorted(unknown))
        known_text = ", ".join(sorted(KNOWN_PROVIDER_NAMES))
        raise ConfigurationError(
            f"알 수 없는 프로바이더가 설정됐어요: {unknown_text}. 지원 목록: {known_text}"
        )

    return resolved


def choose_default_provider(preferred_provider: str | None, enabled_providers: list[str]) -> str:
    if preferred_provider and preferred_provider in enabled_providers:
        return preferred_provider
    return enabled_providers[0]


def build_provider_adapters(
    settings: ProviderRuntimeSettings,
    *,
    enabled_providers: list[str] | None = None,
    copilot_token_override: str | None = None,
) -> list[ProviderAdapter]:
    active_providers = enabled_providers or get_enabled_provider_names(
        settings.enabled_provider_names,
        fallback_default=settings.default_provider_name,
    )

    adapters: list[ProviderAdapter] = []
    for provider_name in active_providers:
        factory = _PROVIDER_FACTORIES.get(provider_name)
        if factory is not None:
            adapters.append(factory(settings, copilot_token_override))

    return adapters
