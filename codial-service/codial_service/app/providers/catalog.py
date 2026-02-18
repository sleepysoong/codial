from __future__ import annotations

from typing import Protocol

from codial_service.app.providers.base import ProviderAdapter
from codial_service.app.providers.http_bridge_adapter import HttpBridgeProviderAdapter
from libs.common.errors import ConfigurationError

KNOWN_PROVIDER_NAMES = {
    "github-copilot-sdk",
}


class ProviderRuntimeSettings(Protocol):
    default_provider_name: str
    enabled_provider_names: str
    copilot_bridge_base_url: str
    copilot_bridge_token: str
    provider_bridge_timeout_seconds: float


def get_enabled_provider_names(raw_value: str, *, fallback_default: str) -> list[str]:
    parsed = _parse_csv_values(raw_value)
    if not parsed:
        parsed = [fallback_default]

    unknown = [provider for provider in parsed if provider not in KNOWN_PROVIDER_NAMES]
    if unknown:
        unknown_text = ", ".join(sorted(unknown))
        known_text = ", ".join(sorted(KNOWN_PROVIDER_NAMES))
        raise ConfigurationError(
            f"알 수 없는 프로바이더가 설정됐어요: {unknown_text}. 지원 목록: {known_text}"
        )

    return parsed


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
        if provider_name == "github-copilot-sdk":
            adapters.append(
                HttpBridgeProviderAdapter(
                    name="github-copilot-sdk",
                    base_url=settings.copilot_bridge_base_url,
                    token=copilot_token_override if copilot_token_override is not None else settings.copilot_bridge_token,
                    timeout_seconds=settings.provider_bridge_timeout_seconds,
                    provider_hint="GitHub Copilot SDK",
                )
            )

    return adapters


def _parse_csv_values(raw_value: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for part in raw_value.split(","):
        normalized = part.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        values.append(normalized)
    return values
