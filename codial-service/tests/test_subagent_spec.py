from __future__ import annotations

from pathlib import Path

from codial_service.app.subagent_spec import discover_subagents, parse_subagent_file


def test_parse_subagent_file_reads_frontmatter_fields(tmp_path: Path) -> None:
    agent_file = tmp_path / "planner.md"
    agent_file.write_text(
        """
---
name: planner
description: 계획 수립 전용이에요.
model: gpt-5
permissionMode: default
maxTurns: 3
skills: [analyze, design]
mcpServers: [default, tools]
hooks:
  Stop:
    - matcher: .*
memory: project
---

사용자 요청을 단계별로 정리해요.
""",
        encoding="utf-8",
    )

    spec = parse_subagent_file(agent_file)
    assert spec.name == "planner"
    assert spec.model == "gpt-5"
    assert spec.max_turns == 3
    assert spec.skills == ["analyze", "design"]
    assert spec.mcp_servers == ["default", "tools"]
    assert spec.memory == "project"
    assert "단계별" in spec.prompt


def test_discover_subagents_last_path_wins_on_name_collision(tmp_path: Path) -> None:
    global_path = tmp_path / "global"
    project_path = tmp_path / "project"
    global_path.mkdir(parents=True)
    project_path.mkdir(parents=True)

    (global_path / "planner.md").write_text(
        "---\nname: planner\nmodel: gpt-4\n---\n전역 설정\n",
        encoding="utf-8",
    )
    (project_path / "planner.md").write_text(
        "---\nname: planner\nmodel: gpt-5\n---\n프로젝트 설정\n",
        encoding="utf-8",
    )

    discovered = discover_subagents([global_path, project_path])
    assert len(discovered) == 1
    assert discovered[0].model == "gpt-5"
