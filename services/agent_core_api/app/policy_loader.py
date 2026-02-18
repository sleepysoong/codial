from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AgentDefaults:
    provider: str | None
    model: str | None
    mcp_enabled: bool | None
    mcp_profile_name: str | None


@dataclass(slots=True)
class PolicySnapshot:
    rules_summary: str
    agents_summary: str
    skills_summary: str
    rules_text: str
    agents_text: str


class PolicyLoader:
    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root)

    def load(self) -> PolicySnapshot:
        rules_path = self._workspace_root / "RULES.md"
        agents_path = self._workspace_root / "AGENTS.md"

        rules_summary = self._read_headline(rules_path)
        agents_summary = self._read_headline(agents_path)
        skills_summary = self._read_skills_summary(self._workspace_root / "skills")

        rules_text = self._read_full_text(rules_path)
        agents_text = self._read_full_text(agents_path)
        return PolicySnapshot(
            rules_summary=rules_summary,
            agents_summary=agents_summary,
            skills_summary=skills_summary,
            rules_text=rules_text,
            agents_text=agents_text,
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

    def _read_full_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _read_skills_summary(self, skills_dir: Path) -> str:
        if not skills_dir.exists() or not skills_dir.is_dir():
            return "스킬 디렉토리가 없어요."
        skill_files = sorted([path.name for path in skills_dir.glob("*.yaml")])
        if not skill_files:
            return "스킬 파일이 없어요."
        return ", ".join(skill_files)


def extract_agent_defaults(agents_text: str) -> AgentDefaults:
    defaults = AgentDefaults(
        provider=None,
        model=None,
        mcp_enabled=None,
        mcp_profile_name=None,
    )

    for raw_line in agents_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue

        key, value = line.split(":", maxsplit=1)
        normalized_key = key.strip().lower()
        normalized_value = value.strip()

        if normalized_key == "default_provider" and normalized_value:
            defaults.provider = normalized_value
        elif normalized_key == "default_model" and normalized_value:
            defaults.model = normalized_value
        elif normalized_key == "default_mcp_enabled" and normalized_value:
            lowered = normalized_value.lower()
            if lowered in {"true", "yes", "1"}:
                defaults.mcp_enabled = True
            elif lowered in {"false", "no", "0"}:
                defaults.mcp_enabled = False
        elif normalized_key == "default_mcp_profile" and normalized_value:
            defaults.mcp_profile_name = normalized_value

    return defaults
