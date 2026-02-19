"""기본 내장 도구를 등록한 ToolRegistry를 생성하는 팩토리예요."""

from __future__ import annotations

from codial_service.app.tools.file_read import FileReadTool
from codial_service.app.tools.file_write import FileWriteTool
from codial_service.app.tools.glob import GlobTool
from codial_service.app.tools.grep import GrepTool
from codial_service.app.tools.registry import ToolRegistry
from codial_service.app.tools.shell import ShellTool
from codial_service.app.tools.string_replace import HashlineEditTool
from codial_service.app.tools.web_fetch import WebFetchTool


def build_default_tool_registry(*, workspace_root: str = ".") -> ToolRegistry:
    """기본 내장 도구가 모두 등록된 `ToolRegistry`를 생성해요.

    Args:
        workspace_root: 파일/셸 도구가 기준으로 사용할 작업 디렉터리예요.

    Returns:
        7개 기본 도구가 등록된 `ToolRegistry` 인스턴스예요.
    """
    registry = ToolRegistry()
    registry.register(WebFetchTool())
    registry.register(ShellTool(workspace_root=workspace_root))
    # FileReadTool과 HashlineEditTool은 registry를 공유해요.
    # FileReadTool이 읽을 때 registry에 mtime을 기록하고,
    # HashlineEditTool은 read 이력이 없거나 파일이 변경됐으면 거부해요.
    registry.register(FileReadTool(workspace_root=workspace_root, registry=registry))
    registry.register(HashlineEditTool(workspace_root=workspace_root, registry=registry))
    registry.register(FileWriteTool(workspace_root=workspace_root))
    registry.register(GlobTool(workspace_root=workspace_root))
    registry.register(GrepTool(workspace_root=workspace_root))
    return registry
