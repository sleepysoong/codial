"""파일을 생성하거나 덮어쓰는 도구예요."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codial_service.app.tools.base import BaseTool, ToolResult


class FileWriteTool(BaseTool):
    """파일에 내용을 기록하는 도구예요. 파일이 없으면 생성하고 있으면 덮어써요."""

    def __init__(self, *, workspace_root: str = ".") -> None:
        self._workspace_root = Path(workspace_root).resolve()

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return (
            "파일에 내용을 기록해요. "
            "파일이 없으면 새로 만들고, 있으면 덮어써요. "
            "필요한 상위 디렉터리도 자동으로 생성해요."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "기록할 파일 경로예요.",
                },
                "content": {
                    "type": "string",
                    "description": "파일에 기록할 텍스트 내용이에요.",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return ToolResult(ok=False, error="path 파라미터가 필요해요.")

        content = arguments.get("content")
        if not isinstance(content, str):
            return ToolResult(ok=False, error="content 파라미터가 필요해요.")

        target = Path(raw_path.strip())
        if not target.is_absolute():
            target = self._workspace_root / target
        target = target.resolve()

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except (PermissionError, OSError) as exc:
            return ToolResult(ok=False, error=f"파일 쓰기에 실패했어요: {exc}")

        return ToolResult(
            ok=True,
            output=f"파일을 기록했어요: {target}",
            metadata={
                "byte_count": len(content.encode("utf-8")),
                "line_count": content.count("\n") + (1 if content and not content.endswith("\n") else 0),
            },
        )
