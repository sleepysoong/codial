from __future__ import annotations

from pathlib import Path

from codial_service.app.skills_spec import discover_claude_skills


def test_discover_claude_skills_reads_frontmatter_name(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "review-pr"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """
---
name: review-pr
description: PR 리뷰를 수행해요.
allowed-tools: Read, Grep
---

# Review
테스트
""",
        encoding="utf-8",
    )

    skills = discover_claude_skills([tmp_path / "skills"])
    assert len(skills) == 1
    assert skills[0].name == "review-pr"
    assert skills[0].allowed_tools == ["Read", "Grep"]


def test_discover_claude_commands_compatibility(tmp_path: Path) -> None:
    command_dir = tmp_path / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "deploy.md").write_text(
        """
---
description: 배포 워크플로우를 수행해요.
disable-model-invocation: true
---

# Deploy
단계 실행
""",
        encoding="utf-8",
    )

    skills = discover_claude_skills([], [tmp_path / "commands"])
    assert len(skills) == 1
    assert skills[0].name == "deploy"
    assert skills[0].disable_model_invocation is True
