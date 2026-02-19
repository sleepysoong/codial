"""파일 내용을 읽는 도구예요.

각 라인에 Hashline 포맷(줄번호:해시| 내용)을 적용하여
LLM이 해시 앵커로 정확한 위치를 지정할 수 있게 해 줘요.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codial_service.app.tools.base import BaseTool, ToolResult
from codial_service.app.tools.hashline import format_lines_with_hash


class FileReadTool(BaseTool):
    """파일 또는 디렉터리 내용을 읽는 도구예요."""

    def __init__(
        self,
        *,
        workspace_root: str = ".",
        max_lines: int = 2000,
        max_bytes: int = 500_000,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._max_lines = max_lines
        self._max_bytes = max_bytes

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return (
            "파일의 텍스트 내용을 Hashline 포맷(줄번호:해시| 내용)으로 읽어요. "
            "각 줄에 내용 기반 2글자 해시 태그가 붙어요. "
            "이 해시를 hashline_edit 도구에서 앵커로 사용해요. "
            "디렉터리 경로를 주면 목록을 반환해요. "
            "offset과 limit으로 범위를 지정할 수 있어요."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "읽을 파일 또는 디렉터리 경로예요. 절대 경로 또는 workspace 기준 상대 경로예요.",
                },
                "offset": {
                    "type": "integer",
                    "description": "읽기 시작할 줄 번호 (1-indexed)예요. 기본값은 1이에요.",
                },
                "limit": {
                    "type": "integer",
                    "description": "읽을 최대 줄 수예요. 기본값은 2000이에요.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return ToolResult(ok=False, error="path 파라미터가 필요해요.")

        target = Path(raw_path.strip())
        if not target.is_absolute():
            target = self._workspace_root / target
        target = target.resolve()

        if not target.exists():
            return ToolResult(ok=False, error=f"경로를 찾을 수 없어요: {target}")

        if target.is_dir():
            return self._read_directory(target)

        return self._read_file(target, arguments)

    def _read_directory(self, target: Path) -> ToolResult:
        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return ToolResult(ok=False, error=f"디렉터리 접근 권한이 없어요: {target}")

        lines: list[str] = []
        for entry in entries:
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")

        return ToolResult(
            ok=True,
            output="\n".join(lines),
            metadata={"type": "directory", "entry_count": len(lines)},
        )

    def _read_file(self, target: Path, arguments: dict[str, Any]) -> ToolResult:
        offset_value = arguments.get("offset", 1)
        offset = max(1, int(offset_value) if isinstance(offset_value, (int, float)) else 1)

        limit_value = arguments.get("limit", self._max_lines)
        limit = max(1, int(limit_value) if isinstance(limit_value, (int, float)) else self._max_lines)
        limit = min(limit, self._max_lines)

        try:
            raw = target.read_bytes()
        except PermissionError:
            return ToolResult(ok=False, error=f"파일 접근 권한이 없어요: {target}")
        except OSError as exc:
            return ToolResult(ok=False, error=f"파일 읽기에 실패했어요: {exc}")

        text = raw[: self._max_bytes].decode("utf-8", errors="replace")
        all_lines = text.splitlines(keepends=True)
        total_lines = len(all_lines)

        start_idx = offset - 1
        end_idx = start_idx + limit
        selected = all_lines[start_idx:end_idx]

        numbered = format_lines_with_hash(
            [line.rstrip() for line in selected],
            start=offset,
        )

        return ToolResult(
            ok=True,
            output="\n".join(numbered),
            metadata={
                "type": "file",
                "total_lines": total_lines,
                "offset": offset,
                "lines_returned": len(selected),
                "byte_count": len(raw),
                "truncated": len(raw) > self._max_bytes,
            },
        )
