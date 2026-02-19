from __future__ import annotations

from pathlib import Path

import pytest
from codial_service.app.codial_rules import CodialRuleStore


@pytest.mark.asyncio
async def test_codial_rule_store_add_and_list(tmp_path: Path) -> None:
    store = CodialRuleStore(workspace_root=str(tmp_path))
    updated = await store.add_rule("출력은 항상 한국어 존댓말로 작성해요.")

    assert updated == ["출력은 항상 한국어 존댓말로 작성해요."]
    assert store.list_rules() == ["출력은 항상 한국어 존댓말로 작성해요."]


@pytest.mark.asyncio
async def test_codial_rule_store_remove_with_invalid_index_raises(tmp_path: Path) -> None:
    store = CodialRuleStore(workspace_root=str(tmp_path))
    await store.add_rule("첫 번째 규칙")

    with pytest.raises(ValueError, match="index_out_of_range"):
        await store.remove_rule(2)


def test_codial_rule_store_reads_existing_codial_file(tmp_path: Path) -> None:
    (tmp_path / "CODIAL.md").write_text(
        "# CODIAL.md\n\n## 규칙 목록\n\n- 하나\n- 둘\n",
        encoding="utf-8",
    )
    store = CodialRuleStore(workspace_root=str(tmp_path))

    assert store.list_rules() == ["하나", "둘"]
