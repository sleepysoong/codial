from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ClaudeSkill:
    name: str
    description: str
    path: str
    argument_hint: str | None
    disable_model_invocation: bool
    user_invocable: bool
    allowed_tools: list[str]
    model: str | None
    context: str | None
    agent: str | None
    markdown_body: str


def parse_claude_skill_file(skill_md_path: Path) -> ClaudeSkill:
    text = skill_md_path.read_text(encoding="utf-8")
    frontmatter, markdown_body = _split_frontmatter(text)

    raw_name = frontmatter.get("name")
    name = raw_name if isinstance(raw_name, str) and raw_name.strip() else skill_md_path.parent.name

    raw_description = frontmatter.get("description")
    description = (
        raw_description.strip()
        if isinstance(raw_description, str) and raw_description.strip()
        else _first_non_empty_line(markdown_body)
    )

    allowed_tools_value = frontmatter.get("allowed-tools")
    allowed_tools = _normalize_allowed_tools(allowed_tools_value)

    return ClaudeSkill(
        name=name,
        description=description,
        path=str(skill_md_path),
        argument_hint=_optional_str(frontmatter.get("argument-hint")),
        disable_model_invocation=_optional_bool(frontmatter.get("disable-model-invocation"), default=False),
        user_invocable=_optional_bool(frontmatter.get("user-invocable"), default=True),
        allowed_tools=allowed_tools,
        model=_optional_str(frontmatter.get("model")),
        context=_optional_str(frontmatter.get("context")),
        agent=_optional_str(frontmatter.get("agent")),
        markdown_body=markdown_body,
    )


def discover_claude_skills(base_paths: list[Path]) -> list[ClaudeSkill]:
    discovered: list[ClaudeSkill] = []
    for base_path in base_paths:
        if not base_path.exists() or not base_path.is_dir():
            continue
        for skill_md in sorted(base_path.glob("*/SKILL.md")):
            discovered.append(parse_claude_skill_file(skill_md))
    return discovered


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    stripped = text.lstrip()
    if not stripped.startswith("---\n"):
        return {}, text

    lines = stripped.splitlines()
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, text

    frontmatter_text = "\n".join(lines[1:end_index])
    markdown_body = "\n".join(lines[end_index + 1 :]).strip()

    loaded = yaml.safe_load(frontmatter_text)
    if isinstance(loaded, dict):
        return loaded, markdown_body
    return {}, markdown_body


def _first_non_empty_line(markdown_body: str) -> str:
    for line in markdown_body.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate[:200]
    return "설명이 없어요."


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _optional_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _normalize_allowed_tools(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip())
        return normalized
    return []
