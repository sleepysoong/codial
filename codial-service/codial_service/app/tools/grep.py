"""파일 내용에서 정규식 패턴을 검색하는 도구예요."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from codial_service.app.tools.base import BaseTool, ToolResult


class GrepTool(BaseTool):
    """파일 내용에서 정규식 패턴을 검색하는 도구예요."""

    def __init__(
        self,
        *,
        workspace_root: str = ".",
        max_results: int = 500,
        max_file_bytes: int = 1_000_000,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._max_results = max_results
        self._max_file_bytes = max_file_bytes

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "파일 내용에서 정규식 패턴을 검색해요. "
            "파일 경로, 줄 번호, 일치하는 줄을 반환해요."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "검색할 정규식 패턴이에요.",
                },
                "path": {
                    "type": "string",
                    "description": "검색 시작 디렉터리예요. 생략 시 workspace 루트를 사용해요.",
                },
                "include": {
                    "type": "string",
                    "description": "검색 대상 파일 glob 패턴이에요. 예: *.py, *.{ts,tsx}",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        raw_pattern = arguments.get("pattern")
        if not isinstance(raw_pattern, str) or not raw_pattern.strip():
            return ToolResult(ok=False, error="pattern 파라미터가 필요해요.")

        try:
            regex = re.compile(raw_pattern.strip())
        except re.error as exc:
            return ToolResult(ok=False, error=f"정규식이 올바르지 않아요: {exc}")

        search_root = self._workspace_root
        raw_path = arguments.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            candidate = Path(raw_path.strip())
            if not candidate.is_absolute():
                candidate = self._workspace_root / candidate
            candidate = candidate.resolve()
            if candidate.is_dir():
                search_root = candidate

        include_pattern = arguments.get("include")
        if isinstance(include_pattern, str) and include_pattern.strip():
            file_glob = include_pattern.strip()
        else:
            file_glob = "**/*"

        try:
            files = sorted(search_root.glob(file_glob))
        except (ValueError, OSError):
            files = []

        results: list[str] = []
        file_match_count = 0

        for file_path in files:
            if not file_path.is_file():
                continue
            if len(results) >= self._max_results:
                break
            try:
                raw = file_path.read_bytes()
                if len(raw) > self._max_file_bytes:
                    continue
                text = raw.decode("utf-8", errors="replace")
            except (PermissionError, OSError):
                continue

            file_had_match = False
            for line_num, line in enumerate(text.splitlines(), start=1):
                if len(results) >= self._max_results:
                    break
                if regex.search(line):
                    results.append(f"{file_path}:{line_num}: {line.rstrip()}")
                    file_had_match = True

            if file_had_match:
                file_match_count += 1

        truncated = len(results) >= self._max_results
        return ToolResult(
            ok=True,
            output="\n".join(results) if results else "(일치하는 내용이 없어요)",
            metadata={
                "match_count": len(results),
                "file_count": file_match_count,
                "truncated": truncated,
            },
        )
