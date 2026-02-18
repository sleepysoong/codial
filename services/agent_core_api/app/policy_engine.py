from __future__ import annotations

from dataclasses import dataclass

from libs.common.errors import ValidationError


@dataclass(slots=True)
class PolicyConstraints:
    allow_providers: set[str]
    deny_providers: set[str]
    allow_models: set[str]
    deny_models: set[str]


def parse_policy_constraints(rules_text: str) -> PolicyConstraints:
    constraints = PolicyConstraints(
        allow_providers=set(),
        deny_providers=set(),
        allow_models=set(),
        deny_models=set(),
    )

    for line in rules_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        parsed = _parse_key_value_line(stripped)
        if parsed is None:
            continue

        key, value = parsed
        values = {item for item in (part.strip() for part in value.split(",")) if item}

        if key == "allow_providers":
            constraints.allow_providers.update(values)
        elif key == "deny_providers":
            constraints.deny_providers.update(values)
        elif key == "allow_models":
            constraints.allow_models.update(values)
        elif key == "deny_models":
            constraints.deny_models.update(values)

    return constraints


def enforce_provider_and_model(provider: str, model: str, constraints: PolicyConstraints) -> None:
    if constraints.allow_providers and provider not in constraints.allow_providers:
        allowed_text = ", ".join(sorted(constraints.allow_providers))
        raise ValidationError(
            f"RULES 정책으로 인해 `{provider}` 프로바이더를 사용할 수 없어요. 허용 목록: {allowed_text}"
        )

    if provider in constraints.deny_providers:
        raise ValidationError(f"RULES 정책으로 인해 `{provider}` 프로바이더를 사용할 수 없어요.")

    if constraints.allow_models and model not in constraints.allow_models:
        allowed_text = ", ".join(sorted(constraints.allow_models))
        raise ValidationError(
            f"RULES 정책으로 인해 `{model}` 모델을 사용할 수 없어요. 허용 목록: {allowed_text}"
        )

    if model in constraints.deny_models:
        raise ValidationError(f"RULES 정책으로 인해 `{model}` 모델을 사용할 수 없어요.")


def _parse_key_value_line(line: str) -> tuple[str, str] | None:
    candidate = line
    if candidate.startswith("-"):
        candidate = candidate[1:].strip()
    if ":" not in candidate:
        return None

    key, value = candidate.split(":", maxsplit=1)
    normalized_key = key.strip().lower()
    normalized_value = value.strip()
    if not normalized_key:
        return None
    return normalized_key, normalized_value
