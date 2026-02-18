from __future__ import annotations

from pathlib import Path

from services.agent_core_api.app.skills_spec import discover_claude_skills


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
