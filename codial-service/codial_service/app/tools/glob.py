"""Glob 패턴으로 파일을 검색하는 도구예요."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codial_service.app.tools.base import BaseTool, ToolResult


class GlobTool(BaseTool):
    """Glob 패턴으로 파일 경로를 검색하는 도구예요."""

    def __init__(
        self,
        *,
        workspace_root: str = ".",
        max_results: int = 1000,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._max_results = max_results

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return (
            "Glob 패턴으로 파일을 검색해요. "
            "예시: '**/*.py', 'src/**/*.ts', '*.json' 등이에요."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob 패턴이에요. 예: **/*.py, src/**/*.ts",
                },
                "path": {
                    "type": "string",
                    "description": "검색 시작 디렉터리예요. 생략 시 workspace 루트를 사용해요.",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        pattern = arguments.get("pattern")
        if not isinstance(pattern, str) or not pattern.strip():
            return ToolResult(ok=False, error="pattern 파라미터가 필요해요.")

        search_root = self._workspace_root
        raw_path = arguments.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            candidate = Path(raw_path.strip())
            if not candidate.is_absolute():
                candidate = self._workspace_root / candidate
            candidate = candidate.resolve()
            if candidate.is_dir():
                search_root = candidate

        try:
            matches = sorted(search_root.glob(pattern.strip()))
        except (ValueError, OSError) as exc:
            return ToolResult(ok=False, error=f"Glob 검색에 실패했어요: {exc}")

        total = len(matches)
        truncated = total > self._max_results
        matches = matches[: self._max_results]

        lines = [str(m) for m in matches]
        return ToolResult(
            ok=True,
            output="\n".join(lines) if lines else "(일치하는 파일이 없어요)",
            metadata={
                "match_count": total,
                "truncated": truncated,
            },
        )
