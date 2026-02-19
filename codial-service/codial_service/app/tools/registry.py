"""내장 도구를 등록하고 조회하는 레지스트리예요."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from codial_service.app.providers.base import ProviderToolSpec
from codial_service.app.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """도구를 이름으로 관리하는 중앙 레지스트리예요.

    file_read/hashline_edit 간의 신선도 보장을 위해
    세션 내 파일 read 이력(파일 경로 → 읽은 시점의 mtime)을 추적해요.
    hashline_edit 호출 시 해당 파일이 이번 세션에서 read된 적 있는지,
    그리고 read 이후 파일이 외부에서 변경되지 않았는지를 검증해요.

    사용법::

        registry = ToolRegistry()
        registry.register(ShellTool(workspace_root="/home/user/project"))
        registry.register(FileReadTool(workspace_root="/home/user/project"))

        # 프로바이더에 전달할 스펙 목록
        specs = registry.to_provider_specs()

        # 이름으로 도구 실행
        result = await registry.call("shell", {"command": "ls"})
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        # 파일 경로(절대) → 마지막으로 file_read한 시점의 mtime (float)
        self._read_mtimes: dict[str, float] = {}

    def register(self, tool: BaseTool) -> None:
        """도구를 레지스트리에 등록해요. 같은 이름이면 덮어씌워요."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """도구를 레지스트리에서 제거해요. 제거 성공 시 True를 반환해요."""
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> BaseTool | None:
        """이름으로 도구를 조회해요."""
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """등록된 모든 도구 이름을 반환해요."""
        return list(self._tools.keys())

    def list_tools(self) -> list[BaseTool]:
        """등록된 모든 도구 인스턴스를 반환해요."""
        return list(self._tools.values())

    def to_provider_specs(self) -> list[ProviderToolSpec]:
        """프로바이더에 전달할 `ProviderToolSpec` 목록을 생성해요."""
        return [
            ProviderToolSpec(
                name=tool.name,
                title=None,
                description=tool.description,
                input_schema=tool.input_schema,
                output_schema=None,
            )
            for tool in self._tools.values()
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """이름으로 도구를 찾아 실행해요.

        등록되지 않은 도구면 실패 `ToolResult`를 반환해요.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, error=f"등록되지 않은 도구예요: {name}")
        try:
            return await tool.execute(arguments)
        except Exception as exc:
            return ToolResult(ok=False, error=f"도구 실행 중 오류가 발생했어요: {exc}")

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    # ── file read 이력 추적 ──────────────────────────────────────────────────

    def notify_file_read(self, abs_path: str) -> None:
        """file_read 도구가 파일을 읽었을 때 mtime을 기록해요.

        Args:
            abs_path: 읽은 파일의 절대 경로예요.
        """
        try:
            self._read_mtimes[abs_path] = os.path.getmtime(abs_path)
        except OSError:
            # 파일이 없거나 권한 없으면 그냥 넘어가요
            pass

    def check_file_edit_allowed(self, abs_path: str) -> str | None:
        """hashline_edit 호출 전 파일의 read 이력을 검증해요.

        다음 두 조건을 모두 만족해야 편집이 허용돼요:
        1. 이번 세션에서 ``file_read``로 읽은 적 있어야 해요.
        2. 마지막 read 이후 파일이 변경되지 않았어야 해요.

        Args:
            abs_path: 편집할 파일의 절대 경로예요.

        Returns:
            편집이 허용되면 ``None``, 거부되면 사유 메시지를 반환해요.
        """
        recorded_mtime = self._read_mtimes.get(abs_path)
        if recorded_mtime is None:
            return (
                f"이 파일은 이번 세션에서 file_read로 읽은 적이 없어요: {abs_path}\n"
                "hashline_edit을 사용하기 전에 반드시 file_read로 파일을 먼저 읽어야 해요."
            )
        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return None  # 파일이 사라진 경우는 execute에서 처리해요

        if current_mtime > recorded_mtime:
            return (
                f"파일이 마지막 file_read 이후 변경됐어요: {abs_path}\n"
                "변경된 파일을 편집하려면 hashline_edit 전에 file_read로 다시 읽어야 해요."
            )
        return None
