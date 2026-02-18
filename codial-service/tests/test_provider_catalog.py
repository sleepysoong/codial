from __future__ import annotations

from dataclasses import dataclass

import pytest
from codial_service.app.providers.catalog import (
    build_provider_adapters,
    choose_default_provider,
    get_enabled_provider_names,
)

from libs.common.errors import ConfigurationError


@dataclass(slots=True)
class _SettingsStub:
    default_provider_name: str = "github-copilot-sdk"
    enabled_provider_names: str = "github-copilot-sdk"
    openai_api_key: str = ""
    openai_request_timeout_seconds: float = 30.0
    codex_bridge_base_url: str = "http://codex.local"
    codex_bridge_token: str = ""
    copilot_bridge_base_url: str = "http://copilot.local"
    copilot_bridge_token: str = ""
    provider_bridge_timeout_seconds: float = 30.0


def test_get_enabled_provider_names_uses_fallback_when_empty() -> None:
    providers = get_enabled_provider_names("", fallback_default="github-copilot-sdk")
    assert providers == ["github-copilot-sdk"]


def test_get_enabled_provider_names_rejects_unknown() -> None:
    with pytest.raises(ConfigurationError):
        get_enabled_provider_names("unknown-provider", fallback_default="github-copilot-sdk")


def test_choose_default_provider_falls_back_to_first_enabled() -> None:
    selected = choose_default_provider("openai-api", ["github-copilot-sdk", "openai-api"])
    assert selected == "openai-api"

    selected_fallback = choose_default_provider("openai-codex", ["github-copilot-sdk"])
    assert selected_fallback == "github-copilot-sdk"


def test_build_provider_adapters_only_builds_enabled_list() -> None:
    settings = _SettingsStub(enabled_provider_names="github-copilot-sdk")
    adapters = build_provider_adapters(settings, copilot_token_override="override-token")
    assert [adapter.name for adapter in adapters] == ["github-copilot-sdk"]
