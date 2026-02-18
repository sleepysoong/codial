from __future__ import annotations

from pathlib import Path

import pytest

from services.agent_core_api.app.claude_memory_loader import load_claude_memories


def test_load_claude_memories_reads_home_and_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_home = tmp_path / "home"
    (fake_home / ".claude").mkdir(parents=True)
    (fake_home / ".claude" / "CLAUDE.md").write_text("home-memory", encoding="utf-8")

    workspace = tmp_path / "repo"
    workspace.mkdir(parents=True)
    (workspace / "CLAUDE.md").write_text("workspace-memory", encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: fake_home)

    snapshot = load_claude_memories(str(workspace))
    assert len(snapshot.loaded_paths) == 2
    assert "home-memory" in snapshot.merged_text
    assert "workspace-memory" in snapshot.merged_text
