from __future__ import annotations

import asyncio
from pathlib import Path


class CodialRuleStore:
    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root)
        self._path = self._workspace_root / "CODIAL.md"
        self._lock = asyncio.Lock()

    def list_rules(self) -> list[str]:
        return self._read_rules()

    def add_rule(self, rule: str) -> list[str]:
        normalized_rule = rule.strip()
        if not normalized_rule:
            return self.list_rules()

        rules = self._read_rules()
        rules.append(normalized_rule)
        self._write_rules(rules)
        return rules

    def remove_rule(self, index: int) -> list[str]:
        rules = self._read_rules()
        if not 1 <= index <= len(rules):
            raise ValueError("index_out_of_range")
        rules.pop(index - 1)
        self._write_rules(rules)
        return rules

    def _read_rules(self) -> list[str]:
        if not self._path.exists():
            return []

        rules: list[str] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                rules.append(stripped[2:].strip())
        return rules

    def _write_rules(self, rules: list[str]) -> None:
        self._workspace_root.mkdir(parents=True, exist_ok=True)
        lines = [
            "# CODIAL.md",
            "",
            "## 규칙 목록",
            "",
        ]
        lines.extend([f"- {rule}" for rule in rules])
        lines.append("")
        self._path.write_text("\n".join(lines), encoding="utf-8")
