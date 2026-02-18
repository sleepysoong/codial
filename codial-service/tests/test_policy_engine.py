from __future__ import annotations

import pytest
from codial_service.app.policy_engine import (
    enforce_provider_and_model,
    parse_policy_constraints,
)

from libs.common.errors import ValidationError


def test_policy_engine_allows_explicit_allowed_provider_and_model() -> None:
    rules_text = "allow_providers: github-copilot-sdk\nallow_models: gpt-5-mini"
    constraints = parse_policy_constraints(rules_text)
    enforce_provider_and_model(
        provider="github-copilot-sdk",
        model="gpt-5-mini",
        constraints=constraints,
        available_skills=set(),
    )


def test_policy_engine_blocks_denied_provider() -> None:
    rules_text = "deny_providers: github-copilot-sdk"
    constraints = parse_policy_constraints(rules_text)
    with pytest.raises(ValidationError):
        enforce_provider_and_model(
            provider="github-copilot-sdk",
            model="gpt-5-mini",
            constraints=constraints,
            available_skills=set(),
        )


def test_policy_engine_blocks_when_required_skill_missing() -> None:
    rules_text = "required_skills: session_bootstrap.yaml"
    constraints = parse_policy_constraints(rules_text)
    with pytest.raises(ValidationError):
        enforce_provider_and_model(
            provider="github-copilot-sdk",
            model="gpt-5-mini",
            constraints=constraints,
            available_skills=set(),
        )
