"""셸 명령을 실행하는 도구예요."""

from __future__ import annotations

import asyncio
from typing import Any

from codial_service.app.tools.base import BaseTool, ToolResult


class ShellTool(BaseTool):
    """셸 명령을 비동기로 실행하는 도구예요."""

    def __init__(
        self,
        *,
        workspace_root: str = ".",
        timeout_seconds: float = 60.0,
        max_output_bytes: int = 500_000,
    ) -> None:
        self._workspace_root = workspace_root
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return (
            "셸 명령을 실행하고 stdout/stderr를 반환해요. "
            "빌드, 테스트, git 등 모든 CLI 작업에 사용할 수 있어요."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "실행할 셸 명령이에요.",
                },
                "workdir": {
                    "type": "string",
                    "description": "작업 디렉터리 경로예요. 생략 시 workspace 루트를 사용해요.",
                },
                "timeout": {
                    "type": "number",
                    "description": "타임아웃 초 단위예요. 생략 시 기본값을 사용해요.",
                },
            },
            "required": ["command"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return ToolResult(ok=False, error="command 파라미터가 필요해요.")

        workdir = arguments.get("workdir")
        if not isinstance(workdir, str) or not workdir.strip():
            workdir = self._workspace_root

        timeout_value = arguments.get("timeout")
        timeout = (
            float(timeout_value)
            if isinstance(timeout_value, (int, float)) and timeout_value > 0
            else self._timeout_seconds
        )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except TimeoutError:
            return ToolResult(ok=False, error=f"명령 실행이 {timeout}초를 초과해 중단됐어요.")
        except OSError as exc:
            return ToolResult(ok=False, error=f"명령 실행에 실패했어요: {exc}")

        stdout = stdout_bytes[: self._max_output_bytes].decode("utf-8", errors="replace")
        stderr = stderr_bytes[: self._max_output_bytes].decode("utf-8", errors="replace")
        exit_code = process.returncode or 0

        combined = stdout
        if stderr:
            combined = f"{stdout}\n--- stderr ---\n{stderr}" if stdout else stderr

        return ToolResult(
            ok=exit_code == 0,
            output=combined,
            error="" if exit_code == 0 else f"프로세스가 종료 코드 {exit_code}로 종료됐어요.",
            metadata={
                "exit_code": exit_code,
                "stdout_bytes": len(stdout_bytes),
                "stderr_bytes": len(stderr_bytes),
            },
        )
