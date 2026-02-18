from __future__ import annotations

from pathlib import Path

import pytest

from libs.common.errors import ValidationError
from services.agent_core_api.app.policy_loader import PolicyLoader
from services.agent_core_api.app.providers.manager import ProviderManager
from services.agent_core_api.app.providers.placeholder_adapter import PlaceholderProviderAdapter


def test_policy_loader_reads_workspace_files(tmp_path: Path) -> None:
    (tmp_path / "RULES.md").write_text("# Rules\n세부 규칙", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agents\n세부 에이전트", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "a.yaml").write_text("name: a", encoding="utf-8")
    (skills_dir / "b.yaml").write_text("name: b", encoding="utf-8")

    snapshot = PolicyLoader(workspace_root=str(tmp_path)).load()
    assert snapshot.rules_summary == "# Rules"
    assert snapshot.agents_summary == "# Agents"
    assert snapshot.skills_summary == "a.yaml, b.yaml"


def test_provider_manager_rejects_unknown_provider() -> None:
    manager = ProviderManager(adapters=[PlaceholderProviderAdapter(name="openai-codex", description="테스트")])
    with pytest.raises(ValidationError):
        manager.resolve("unknown-provider")
