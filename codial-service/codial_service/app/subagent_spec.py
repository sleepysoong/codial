from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codial_service.app.utils import normalize_str_list, split_frontmatter


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


def default_subagent_search_paths(workspace_root: str | Path) -> list[Path]:
    """서브에이전트 탐색에 사용할 기본 경로 목록을 반환해요.

    글로벌 경로(``~/.claude/agents``)를 먼저, 프로젝트 경로를 나중에 넣어요.
    프로젝트 경로가 같은 이름의 에이전트를 덮어써요.

    Args:
        workspace_root: 프로젝트 루트 경로예요.

    Returns:
        ``[global_agents, project_agents]`` 형식의 경로 목록이에요.
    """
    global_agents = Path.home() / ".claude" / "agents"
    project_agents = Path(workspace_root) / ".claude" / "agents"
    return [global_agents, project_agents]


def parse_subagent_file(file_path: Path) -> SubagentSpec:
    content = file_path.read_text(encoding="utf-8")
    frontmatter, prompt = split_frontmatter(content)

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
        tools=normalize_str_list(frontmatter.get("tools")),
        disallowed_tools=normalize_str_list(frontmatter.get("disallowedTools")),
        model=_normalize_model(frontmatter.get("model")),
        permission_mode=_normalize_permission(frontmatter.get("permissionMode")),
        max_turns=_normalize_int(frontmatter.get("maxTurns")),
        skills=normalize_str_list(frontmatter.get("skills")),
        mcp_servers=_normalize_mcp_servers(frontmatter.get("mcpServers")),
        hooks=_normalize_hooks(frontmatter.get("hooks")),
        memory=_normalize_optional_str(frontmatter.get("memory")),
        source_path=str(file_path),
    )


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
