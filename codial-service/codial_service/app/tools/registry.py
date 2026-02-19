"""내장 도구를 등록하고 조회하는 레지스트리예요."""

from __future__ import annotations

from typing import Any

from codial_service.app.providers.base import ProviderToolSpec
from codial_service.app.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """도구를 이름으로 관리하는 중앙 레지스트리예요.

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
