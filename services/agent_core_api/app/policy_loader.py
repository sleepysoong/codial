from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PolicySnapshot:
    rules_summary: str
    agents_summary: str
    skills_summary: str


class PolicyLoader:
    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root)

    def load(self) -> PolicySnapshot:
        rules_summary = self._read_headline(self._workspace_root / "RULES.md")
        agents_summary = self._read_headline(self._workspace_root / "AGENTS.md")
        skills_summary = self._read_skills_summary(self._workspace_root / "skills")
        return PolicySnapshot(
            rules_summary=rules_summary,
            agents_summary=agents_summary,
            skills_summary=skills_summary,
        )

    def _read_headline(self, path: Path) -> str:
        if not path.exists():
            return "파일이 없어요."
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:200]
        return "내용이 비어 있어요."

    def _read_skills_summary(self, skills_dir: Path) -> str:
        if not skills_dir.exists() or not skills_dir.is_dir():
            return "스킬 디렉토리가 없어요."
        skill_files = sorted([path.name for path in skills_dir.glob("*.yaml")])
        if not skill_files:
            return "스킬 파일이 없어요."
        return ", ".join(skill_files)
