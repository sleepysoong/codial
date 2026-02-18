from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class SubagentSpec:
    name: str
    description: str
    prompt: str
    tools: list[str]
    disallowed_tools: list[str]
    model: str
    permission_mode: str
    max_turns: int | None
    skills: list[str]
    mcp_servers: list[str]
    hooks: dict[str, list[dict[str, Any]]]
    memory: str | None
    source_path: str


def discover_subagents(base_paths: list[Path]) -> list[SubagentSpec]:
    found: dict[str, SubagentSpec] = {}
    for base_path in base_paths:
        if not base_path.exists() or not base_path.is_dir():
            continue
        for file_path in sorted(base_path.glob("*.md")):
            spec = parse_subagent_file(file_path)
            found[spec.name] = spec
    return list(found.values())


def parse_subagent_file(file_path: Path) -> SubagentSpec:
    content = file_path.read_text(encoding="utf-8")
    frontmatter, prompt = _split_frontmatter(content)

    name_value = frontmatter.get("name")
    description_value = frontmatter.get("description")

    name = name_value if isinstance(name_value, str) and name_value.strip() else file_path.stem
    description = (
        description_value.strip()
        if isinstance(description_value, str) and description_value.strip()
        else "설명이 없어요."
    )

    return SubagentSpec(
        name=name,
        description=description,
        prompt=prompt,
        tools=_normalize_str_list(frontmatter.get("tools")),
        disallowed_tools=_normalize_str_list(frontmatter.get("disallowedTools")),
        model=_normalize_model(frontmatter.get("model")),
        permission_mode=_normalize_permission(frontmatter.get("permissionMode")),
        max_turns=_normalize_int(frontmatter.get("maxTurns")),
        skills=_normalize_str_list(frontmatter.get("skills")),
        mcp_servers=_normalize_mcp_servers(frontmatter.get("mcpServers")),
        hooks=_normalize_hooks(frontmatter.get("hooks")),
        memory=_normalize_optional_str(frontmatter.get("memory")),
        source_path=str(file_path),
    )


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    stripped = content.lstrip()
    if not stripped.startswith("---\n"):
        return {}, content.strip()

    lines = stripped.splitlines()
    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, content.strip()

    frontmatter_text = "\n".join(lines[1:end_index])
    prompt = "\n".join(lines[end_index + 1 :]).strip()
    loaded = yaml.safe_load(frontmatter_text)
    if isinstance(loaded, dict):
        return loaded, prompt
    return {}, prompt


def _normalize_str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
        return result
    return []


def _normalize_model(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "inherit"


def _normalize_permission(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "default"


def _normalize_int(value: object) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    return None


def _normalize_mcp_servers(value: object) -> list[str]:
    if isinstance(value, list):
        servers: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                servers.append(item.strip())
            elif isinstance(item, dict):
                for key in item:
                    if isinstance(key, str):
                        servers.append(key)
        return servers
    return []


def _normalize_hooks(value: object) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, list[dict[str, Any]]] = {}
    for event_name, entries in value.items():
        if not isinstance(event_name, str) or not isinstance(entries, list):
            continue
        event_entries: list[dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, dict):
                event_entries.append(entry)
        normalized[event_name] = event_entries
    return normalized


def _normalize_optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
