from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ClaudeMemorySnapshot:
    loaded_paths: list[str]
    merged_text: str


def load_claude_memories(workspace_root: str) -> ClaudeMemorySnapshot:
    workspace_path = Path(workspace_root).resolve()
    candidates: list[Path] = []

    home_memory = Path.home() / ".claude" / "CLAUDE.md"
    if home_memory.exists() and home_memory.is_file():
        candidates.append(home_memory)

    current = workspace_path
    while True:
        candidate = current / "CLAUDE.md"
        if candidate.exists() and candidate.is_file():
            candidates.append(candidate)

        if current.parent == current:
            break
        current = current.parent

    merged_parts: list[str] = []
    loaded_paths: list[str] = []
    for path in candidates:
        loaded_paths.append(str(path))
        merged_parts.append(path.read_text(encoding="utf-8"))

    merged_text = "\n\n".join(merged_parts)
    return ClaudeMemorySnapshot(loaded_paths=loaded_paths, merged_text=merged_text)
