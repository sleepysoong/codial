"""Hashline 기반 파일 편집 도구예요.

기존 string_replace(문자열 치환) 방식 대신 **해시 앵커** 기반으로
수정할 라인 범위를 지정해요. file_read가 출력하는 ``줄번호:해시| 내용``
포맷의 해시를 앵커로 사용하므로 공백/들여쓰기 불일치 문제가 사라져요.

사용 흐름:
    1. ``file_read``로 파일을 읽어서 각 줄의 해시를 확인해요. (필수)
    2. 수정할 시작/끝 줄의 해시를 ``start_hash``/``end_hash``로 지정해요.
    3. ``new_content``에 대체할 새 코드를 작성해요.
    4. 지정 범위가 새 코드로 교체돼요.

주의: file_read 없이 hashline_edit을 호출하면 거부돼요.
      파일이 변경된 이후에도 다시 file_read를 호출해야 해요.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from codial_service.app.tools.base import BaseTool, ToolResult
from codial_service.app.tools.hashline import (
    build_hash_to_lineno_map,
    format_lines_with_hash,
    resolve_hash_to_index,
)

if TYPE_CHECKING:
    from codial_service.app.tools.registry import ToolRegistry


class HashlineEditTool(BaseTool):
    """해시 앵커 기반으로 파일의 특정 라인 범위를 교체하는 도구예요."""

    def __init__(self, *, workspace_root: str = ".", registry: ToolRegistry | None = None) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._registry = registry

    @property
    def name(self) -> str:
        return "hashline_edit"

    @property
    def description(self) -> str:
        return (
            "⚠️ 반드시 file_read로 파일을 먼저 읽은 후에만 호출할 수 있어요. "
            "file_read 없이 호출하면 오류가 발생해요. "
            "파일이 수정된 이후에도 다시 file_read로 읽어야 해요. "
            "file_read의 Hashline 포맷(줄번호:해시| 내용)에서 확인한 "
            "해시 앵커를 사용하여 파일의 특정 라인 범위를 새 코드로 교체해요. "
            "start_hash부터 end_hash까지의 라인이 new_content로 대체돼요. "
            "단일 라인 수정 시 start_hash와 end_hash에 같은 값을 넣어요. "
            "라인을 삭제하려면 new_content를 빈 문자열로 설정해요. "
            "새 라인을 삽입하려면 insert_after_hash를 사용해요."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "수정할 파일 경로예요.",
                },
                "start_hash": {
                    "type": "string",
                    "description": (
                        "교체 시작 라인의 해시예요. "
                        "file_read 출력에서 '줄번호:해시| 내용' 형식의 해시 부분이에요."
                    ),
                },
                "end_hash": {
                    "type": "string",
                    "description": (
                        "교체 끝 라인의 해시예요. "
                        "start_hash와 같으면 단일 라인을 교체해요."
                    ),
                },
                "new_content": {
                    "type": "string",
                    "description": (
                        "대체할 새 코드예요. "
                        "빈 문자열이면 해당 범위를 삭제해요."
                    ),
                },
                "insert_after_hash": {
                    "type": "string",
                    "description": (
                        "이 해시 뒤에 new_content를 삽입해요. "
                        "start_hash/end_hash 대신 사용하는 삽입 전용 모드예요."
                    ),
                },
                "start_lineno": {
                    "type": "integer",
                    "description": (
                        "해시 충돌(같은 해시가 여러 줄) 시 "
                        "모호성을 해소하기 위한 시작 줄 번호 힌트(1-indexed)예요."
                    ),
                },
                "end_lineno": {
                    "type": "integer",
                    "description": (
                        "해시 충돌 시 끝 줄 번호 힌트(1-indexed)예요."
                    ),
                },
            },
            "required": ["path", "new_content"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        # ── 경로 검증 ──
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return ToolResult(ok=False, error="path 파라미터가 필요해요.")

        target = Path(raw_path.strip())
        if not target.is_absolute():
            target = self._workspace_root / target
        target = target.resolve()

        if not target.is_file():
            return ToolResult(ok=False, error=f"파일을 찾을 수 없어요: {target}")

        # ── file_read 이력 검증 ──
        if self._registry is not None:
            deny_reason = self._registry.check_file_edit_allowed(str(target))
            if deny_reason is not None:
                return ToolResult(ok=False, error=deny_reason)

        # ── 파일 읽기 ──
        try:
            content = target.read_text(encoding="utf-8")
        except (PermissionError, OSError) as exc:
            return ToolResult(ok=False, error=f"파일 읽기에 실패했어요: {exc}")

        lines = content.splitlines(keepends=True)
        hash_map = build_hash_to_lineno_map(
            [line.rstrip("\n").rstrip("\r") for line in lines]
        )

        new_content: str = arguments.get("new_content", "")
        if not isinstance(new_content, str):
            return ToolResult(ok=False, error="new_content 파라미터가 필요해요.")

        insert_after = arguments.get("insert_after_hash")

        # ── 모드 분기: 삽입 vs 교체 ──
        if insert_after is not None:
            return self._handle_insert(
                target, lines, hash_map, insert_after, new_content, arguments
            )

        return self._handle_replace(
            target, lines, hash_map, new_content, arguments
        )

    def _handle_insert(
        self,
        target: Path,
        lines: list[str],
        hash_map: dict[str, list[int]],
        insert_after: str,
        new_content: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """``insert_after_hash`` 뒤에 새 내용을 삽입해요."""
        hint = arguments.get("start_lineno")
        hint_idx = (hint - 1) if isinstance(hint, int) and hint >= 1 else None
        idx = resolve_hash_to_index(insert_after, hash_map, hint_lineno=hint_idx)

        if idx is None:
            return ToolResult(
                ok=False,
                error=f"insert_after_hash '{insert_after}'에 해당하는 라인을 찾을 수 없어요.",
            )

        # 삽입할 새 라인 준비 (마지막에 개행 보장)
        new_lines = new_content.splitlines(keepends=True)
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        result_lines = lines[: idx + 1] + new_lines + lines[idx + 1 :]
        return self._write_and_respond(target, result_lines, "삽입", idx + 1, len(new_lines))

    def _handle_replace(
        self,
        target: Path,
        lines: list[str],
        hash_map: dict[str, list[int]],
        new_content: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """``start_hash``~``end_hash`` 범위를 교체해요."""
        start_hash = arguments.get("start_hash")
        end_hash = arguments.get("end_hash")

        if not isinstance(start_hash, str) or not start_hash.strip():
            return ToolResult(ok=False, error="start_hash 파라미터가 필요해요 (삽입 모드는 insert_after_hash를 사용해요).")
        if not isinstance(end_hash, str) or not end_hash.strip():
            return ToolResult(ok=False, error="end_hash 파라미터가 필요해요.")

        # 힌트로 모호성 해소
        start_hint = arguments.get("start_lineno")
        start_hint_idx = (start_hint - 1) if isinstance(start_hint, int) and start_hint >= 1 else None

        end_hint = arguments.get("end_lineno")
        end_hint_idx = (end_hint - 1) if isinstance(end_hint, int) and end_hint >= 1 else None

        start_idx = resolve_hash_to_index(start_hash, hash_map, hint_lineno=start_hint_idx)
        if start_idx is None:
            return ToolResult(
                ok=False,
                error=f"start_hash '{start_hash}'에 해당하는 라인을 찾을 수 없어요.",
            )

        end_idx = resolve_hash_to_index(end_hash, hash_map, hint_lineno=end_hint_idx)
        if end_idx is None:
            return ToolResult(
                ok=False,
                error=f"end_hash '{end_hash}'에 해당하는 라인을 찾을 수 없어요.",
            )

        # start가 end보다 뒤에 있으면 스왑
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        # 교체할 새 라인 준비
        if new_content:
            new_lines = new_content.splitlines(keepends=True)
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
        else:
            new_lines = []

        replaced_count = end_idx - start_idx + 1
        result_lines = lines[:start_idx] + new_lines + lines[end_idx + 1 :]

        action = "삭제" if not new_lines else "교체"
        return self._write_and_respond(target, result_lines, action, start_idx, replaced_count)

    def _write_and_respond(
        self,
        target: Path,
        result_lines: list[str],
        action: str,
        affected_start: int,
        affected_count: int,
    ) -> ToolResult:
        """결과를 파일에 쓰고 변경된 부분의 미리보기를 반환해요."""
        new_full = "".join(result_lines)

        try:
            target.write_text(new_full, encoding="utf-8")
        except (PermissionError, OSError) as exc:
            return ToolResult(ok=False, error=f"파일 쓰기에 실패했어요: {exc}")

        # 변경 후 주변 5줄 미리보기 (hashline 포맷)
        preview_start = max(0, affected_start - 2)
        preview_end = min(len(result_lines), affected_start + affected_count + 2)
        preview_slice = [line.rstrip("\n").rstrip("\r") for line in result_lines[preview_start:preview_end]]
        preview = format_lines_with_hash(preview_slice, start=preview_start + 1)

        return ToolResult(
            ok=True,
            output=(
                f"{affected_count}개 라인을 {action}했어요.\n"
                f"--- 변경 후 미리보기 ---\n"
                + "\n".join(preview)
            ),
            metadata={
                "action": action,
                "affected_start": affected_start + 1,  # 1-indexed
                "affected_count": affected_count,
                "total_lines": len(result_lines),
            },
        )
