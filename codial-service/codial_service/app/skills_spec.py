from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codial_service.app.utils import normalize_str_list, split_frontmatter


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
    frontmatter, markdown_body = split_frontmatter(text)

    raw_name = frontmatter.get("name")
    name = raw_name if isinstance(raw_name, str) and raw_name.strip() else skill_md_path.parent.name

    raw_description = frontmatter.get("description")
    description = (
        raw_description.strip()
        if isinstance(raw_description, str) and raw_description.strip()
        else _first_non_empty_line(markdown_body)
    )

    allowed_tools_value = frontmatter.get("allowed-tools")
    allowed_tools = normalize_str_list(allowed_tools_value)

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


def parse_claude_command_file(command_md_path: Path) -> ClaudeSkill:
    text = command_md_path.read_text(encoding="utf-8")
    frontmatter, markdown_body = split_frontmatter(text)

    raw_name = frontmatter.get("name")
    default_name = command_md_path.stem
    name = raw_name if isinstance(raw_name, str) and raw_name.strip() else default_name

    raw_description = frontmatter.get("description")
    description = (
        raw_description.strip()
        if isinstance(raw_description, str) and raw_description.strip()
        else _first_non_empty_line(markdown_body)
    )

    allowed_tools_value = frontmatter.get("allowed-tools")
    allowed_tools = normalize_str_list(allowed_tools_value)

    return ClaudeSkill(
        name=name,
        description=description,
        path=str(command_md_path),
        argument_hint=_optional_str(frontmatter.get("argument-hint")),
        disable_model_invocation=_optional_bool(frontmatter.get("disable-model-invocation"), default=False),
        user_invocable=_optional_bool(frontmatter.get("user-invocable"), default=True),
        allowed_tools=allowed_tools,
        model=_optional_str(frontmatter.get("model")),
        context=_optional_str(frontmatter.get("context")),
        agent=_optional_str(frontmatter.get("agent")),
        markdown_body=markdown_body,
    )


def discover_claude_skills(
    skill_base_paths: list[Path],
    command_base_paths: list[Path] | None = None,
) -> list[ClaudeSkill]:
    discovered: list[ClaudeSkill] = []
    for base_path in skill_base_paths:
        if not base_path.exists() or not base_path.is_dir():
            continue
        for skill_md in sorted(base_path.glob("*/SKILL.md")):
            discovered.append(parse_claude_skill_file(skill_md))

    if command_base_paths is not None:
        for command_path in command_base_paths:
            if not command_path.exists() or not command_path.is_dir():
                continue
            for command_md in sorted(command_path.glob("*.md")):
                discovered.append(parse_claude_command_file(command_md))

    deduped: dict[str, ClaudeSkill] = {}
    for skill in discovered:
        deduped[skill.name] = skill
    return list(deduped.values())


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


