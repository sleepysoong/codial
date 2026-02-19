from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from codial_service.app.mcp_protocol import McpInitializeResult, McpTool
from codial_service.app.policy_loader import PolicyLoader, PolicySnapshot
from codial_service.app.providers.base import (
    ProviderAdapter,
    ProviderRequest,
    ProviderResponse,
    ProviderToolRequest,
)
from codial_service.app.tools.defaults import build_default_tool_registry
from codial_service.app.turn_worker import TurnWorkerPool


class _FakeSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)


@dataclass(slots=True)
class _IngestResult:
    summary: str


class _FakeAttachmentIngestor:
    async def ingest(
        self,
        *,
        session_id: str,
        turn_id: str,
        attachments: list[Any],
    ) -> _IngestResult:
        del session_id, turn_id, attachments
        return _IngestResult(summary="첨부파일이 없어서 다운로드를 건너뛰었어요.")


class _FakePolicyLoader(PolicyLoader):
    def __init__(self) -> None:
        pass

    def load(self) -> PolicySnapshot:
        return PolicySnapshot(
            rules_summary="RULES 없음",
            agents_summary="AGENTS 없음",
            skills_summary="스킬 없음",
            rules_text="",
            agents_text="",
            available_skills=[],
            system_memory_summary="CLAUDE.md 메모리가 없어요.",
            claude_memory_text="",
        )


class _FakeMcpClient:
    def __init__(self) -> None:
        self.tool_calls: list[tuple[str, dict[str, Any]]] = []

    async def initialize(self, *, client_name: str, client_version: str) -> McpInitializeResult:
        del client_name, client_version
        return McpInitializeResult(
            server_name="fake-mcp",
            server_version="1.0.0",
            protocol_version="2025-11-25",
            server_capabilities={"tools": {}},
            instructions=None,
            session_id="fake-session",
        )

    async def ensure_initialized(self, *, client_name: str, client_version: str) -> McpInitializeResult:
        return await self.initialize(client_name=client_name, client_version=client_version)

    async def list_tools(self) -> list[McpTool]:
        return [
            McpTool(
                name="read_file",
                title="파일 읽기",
                description="파일 내용을 읽어요.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ]

    async def list_prompts(self) -> list[Any]:
        return []

    async def list_resources(self) -> list[Any]:
        return []

    async def list_resource_templates(self) -> list[Any]:
        return []

    async def ping(self) -> None:
        return None

    async def call_tool(self, *, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.tool_calls.append((name, arguments))
        return {"ok": True, "tool": name, "arguments": arguments}


class _ToolCallingProviderAdapter(ProviderAdapter):
    name = "github-copilot-sdk"

    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if request.tool_call_round == 0:
            return ProviderResponse(
                output_text="",
                decision_summary="도구 호출이 필요해요.",
                tool_requests=[
                    ProviderToolRequest(
                        name="read_file",
                        arguments={"path": "README.md"},
                        call_id="call-1",
                    )
                ],
            )

        assert request.tool_results
        return ProviderResponse(
            output_text="도구 결과를 반영해서 답변했어요.",
            decision_summary="도구 실행 결과를 반영했어요.",
        )


async def _wait_for_event(sink: _FakeSink, event_type: str, *, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if any(event.get("type") == event_type for event in sink.events):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"{event_type} 이벤트를 시간 안에 받지 못했어요.")


@pytest.mark.asyncio
async def test_turn_worker_executes_mcp_tool_calls_and_reinjects_results(tmp_path: Path) -> None:
    sink = _FakeSink()
    ingestor = _FakeAttachmentIngestor()
    mcp_client = _FakeMcpClient()
    adapter = _ToolCallingProviderAdapter()
    provider_adapters = {adapter.name: adapter}
    policy_loader = _FakePolicyLoader()

    worker_pool = TurnWorkerPool(
        sink=cast(Any, sink),
        attachment_ingestor=cast(Any, ingestor),
        mcp_client=cast(Any, mcp_client),
        provider_adapters=cast(Any, provider_adapters),
        policy_loader=cast(Any, policy_loader),
        tool_registry=build_default_tool_registry(workspace_root=str(tmp_path)),
        worker_count=1,
        workspace_root=str(tmp_path),
    )

    await worker_pool.start()
    try:
        await worker_pool.enqueue(
            session_id="session-1",
            user_id="user-1",
            text="README를 읽고 요약해줘",
            attachments=[],
            provider="github-copilot-sdk",
            model="gpt-5",
            mcp_enabled=True,
            mcp_profile_name="default",
            subagent_name=None,
        )
        await _wait_for_event(sink, "final")
    finally:
        await worker_pool.stop()

    assert len(adapter.requests) == 2
    # 내장 도구 + MCP 도구가 함께 전달되었는지 확인
    all_tool_names = {t.name for t in adapter.requests[0].tool_specs}
    assert "read_file" in all_tool_names  # MCP 도구
    assert "shell" in all_tool_names      # 내장 도구
    assert "file_read" in all_tool_names  # 내장 도구
    # read_file은 내장 도구가 아니므로 MCP로 실행됨
    assert adapter.requests[1].tool_results
    assert adapter.requests[1].tool_results[0].name == "read_file"
    assert adapter.requests[1].tool_results[0].ok is True
    assert mcp_client.tool_calls == [("read_file", {"path": "README.md"})]
    assert any(
        event.get("type") == "action"
        and "MCP 도구 `read_file` 호출을 성공적으로 완료했어요." in str(event.get("payload", {}).get("text", ""))
        for event in sink.events
    )
