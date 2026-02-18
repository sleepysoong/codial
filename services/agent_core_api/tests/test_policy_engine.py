from __future__ import annotations

import pytest

from libs.common.errors import ValidationError
from services.agent_core_api.app.policy_engine import (
    enforce_provider_and_model,
    parse_policy_constraints,
)


def test_policy_engine_allows_explicit_allowed_provider_and_model() -> None:
    rules_text = "allow_providers: openai-api, github-copilot-sdk\nallow_models: gpt-5-mini"
    constraints = parse_policy_constraints(rules_text)
    enforce_provider_and_model(
        provider="openai-api",
        model="gpt-5-mini",
        constraints=constraints,
    )


def test_policy_engine_blocks_denied_provider() -> None:
    rules_text = "deny_providers: openai-codex"
    constraints = parse_policy_constraints(rules_text)
    with pytest.raises(ValidationError):
        enforce_provider_and_model(
            provider="openai-codex",
            model="gpt-5-mini",
            constraints=constraints,
        )
