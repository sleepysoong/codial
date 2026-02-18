from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codial_service.app.attachment_ingestor import AttachmentIngestor
from codial_service.app.event_sink import GatewayEventSink
from codial_service.app.mcp_client import McpClient
from codial_service.app.models import TurnAttachment
from codial_service.app.policy_engine import (
    enforce_provider_and_model,
    parse_policy_constraints,
)
from codial_service.app.policy_loader import PolicyLoader
from codial_service.app.providers.base import (
    ProviderRequest,
    ProviderToolResult,
    ProviderToolSpec,
)
from codial_service.app.providers.manager import ProviderManager
from codial_service.app.subagent_spec import SubagentSpec, discover_subagents
from libs.common.errors import UpstreamTransientError
from libs.common.logging import get_logger

logger = get_logger("codial_service.turn_worker")
MAX_TOOL_CALL_ROUNDS = 5


@dataclass(slots=True)
class TurnTask:
    turn_id: str
    session_id: str
    user_id: str
    text: str
    attachments: list[TurnAttachment]
    provider: str
    model: str
    mcp_enabled: bool
    mcp_profile_name: str | None
    subagent_name: str | None


class TurnWorkerPool:
    def __init__(
        self,
        sink: GatewayEventSink,
        attachment_ingestor: AttachmentIngestor,
        mcp_client: McpClient | None,
        provider_manager: ProviderManager,
        policy_loader: PolicyLoader,
        worker_count: int,
        workspace_root: str,
    ) -> None:
        self._sink = sink
        self._attachment_ingestor = attachment_ingestor
        self._mcp_client = mcp_client
        self._provider_manager = provider_manager
        self._policy_loader = policy_loader
        self._worker_count = worker_count
        self._workspace_root = Path(workspace_root)
        self._queue: asyncio.Queue[TurnTask] = asyncio.Queue(maxsize=1000)
        self._tasks: list[asyncio.Task[None]] = []
        self._closing = False

    async def start(self) -> None:
        if self._tasks:
            return
        for idx in range(self._worker_count):
            self._tasks.append(asyncio.create_task(self._worker_loop(idx)))

    async def stop(self) -> None:
        self._closing = True
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    async def enqueue(
        self,
        session_id: str,
        user_id: str,
        text: str,
        attachments: list[TurnAttachment],
        provider: str,
        model: str,
        mcp_enabled: bool,
        mcp_profile_name: str | None,
        subagent_name: str | None,
    ) -> str:
        turn_id = str(uuid.uuid4())
        task = TurnTask(
            turn_id=turn_id,
            session_id=session_id,
            user_id=user_id,
            text=text,
            attachments=attachments,
            provider=provider,
            model=model,
            mcp_enabled=mcp_enabled,
            mcp_profile_name=mcp_profile_name,
            subagent_name=subagent_name,
        )
        await self._queue.put(task)
        return turn_id

    def _load_subagent_spec(self, subagent_name: str) -> SubagentSpec | None:
        global_agents = Path.home() / ".claude" / "agents"
        project_agents = self._workspace_root / ".claude" / "agents"
        specs = discover_subagents([global_agents, project_agents])
        for spec in specs:
            if spec.name == subagent_name:
                return spec
        return None

    async def _worker_loop(self, worker_index: int) -> None:
        while not self._closing:
            task = await self._queue.get()
            try:
                await self._process_task(task)
            except Exception as exc:
                logger.exception(
                    "turn_processing_failed",
                    worker_index=worker_index,
                    turn_id=task.turn_id,
                    error=str(exc),
                )
                await self._emit(task, "error", {"text": "요청 처리 중 오류가 발생했어요."})
            finally:
                self._queue.task_done()

    async def _process_task(self, task: TurnTask) -> None:
        policy_snapshot = self._policy_loader.load()
        policy_constraints = parse_policy_constraints(policy_snapshot.rules_text)
        attachment_count = len(task.attachments)
        effective_text = task.text
        effective_model = task.model
        effective_mcp_enabled = task.mcp_enabled
        effective_mcp_profile_name = task.mcp_profile_name
        effective_claude_memory_summary = policy_snapshot.claude_memory_summary

        await self._emit(
            task,
            "plan",
            {
                "text": (
                    "요청을 분석하고 실행 계획을 준비하고 있어요. "
                    f"프로바이더=`{task.provider}`, 모델=`{task.model}`, "
                    f"서브에이전트=`{task.subagent_name or '없음'}`, 첨부파일={attachment_count}개"
                )
            },
        )
        await self._emit(
            task,
            "action",
            {
                "text": (
                    "정책 파일을 로드했어요. "
                    f"CLAUDE.md=`{policy_snapshot.claude_memory_summary}`, "
                    f"RULES=`{policy_snapshot.rules_summary}`, "
                    f"AGENTS=`{policy_snapshot.agents_summary}`, "
                    f"SKILLS=`{policy_snapshot.skills_summary}`"
                )
            },
        )

        if task.subagent_name:
            subagent = self._load_subagent_spec(task.subagent_name)
            if subagent is None:
                await self._emit(
                    task,
                    "action",
                    {
                        "text": (
                            f"서브에이전트 `{task.subagent_name}`를 찾지 못했어요. "
                            "기본 세션 설정으로 계속 진행해요."
                        )
                    },
                )
            else:
                if subagent.model != "inherit":
                    effective_model = subagent.model
                if subagent.prompt:
                    if effective_text:
                        effective_text = f"{subagent.prompt}\n\n사용자 요청:\n{effective_text}"
                    else:
                        effective_text = subagent.prompt
                if subagent.mcp_servers:
                    effective_mcp_enabled = True
                    if not effective_mcp_profile_name:
                        effective_mcp_profile_name = subagent.mcp_servers[0]
                if subagent.memory:
                    effective_claude_memory_summary = (
                        f"{effective_claude_memory_summary}, subagent-memory={subagent.memory}"
                    )

                mcp_state = "활성" if effective_mcp_enabled else "비활성"
                await self._emit(
                    task,
                    "action",
                    {
                        "text": (
                            f"서브에이전트 `{subagent.name}`를 적용했어요. "
                            f"적용 모델=`{effective_model}`, MCP=`{mcp_state}`"
                        )
                    },
                )

        ingest_result = await self._attachment_ingestor.ingest(
            session_id=task.session_id,
            turn_id=task.turn_id,
            attachments=task.attachments,
        )
        await self._emit(task, "action", {"text": ingest_result.summary})

        mcp_tools: list[ProviderToolSpec] = []
        if effective_mcp_enabled and self._mcp_client is not None:
            initialize_result = await self._mcp_client.initialize(
                client_name="codial-core",
                client_version="0.1.0",
            )
            server_name = initialize_result.server_name or "알 수 없는 서버"
            protocol_version = initialize_result.protocol_version or "미확인"

            tools_count = 0
            prompts_count = 0
            resources_count = 0
            template_count = 0

            try:
                raw_tools = await self._mcp_client.list_tools()
                tools_count = len(raw_tools)
                mcp_tools = [
                    ProviderToolSpec(
                        name=tool.name,
                        title=tool.title,
                        description=tool.description,
                        input_schema=tool.input_schema,
                        output_schema=tool.output_schema,
                    )
                    for tool in raw_tools
                ]
            except UpstreamTransientError as exc:
                logger.warning("mcp_tools_list_failed", session_id=task.session_id, error=str(exc))

            try:
                prompts_count = len(await self._mcp_client.list_prompts())
            except UpstreamTransientError as exc:
                logger.warning("mcp_prompts_list_failed", session_id=task.session_id, error=str(exc))

            try:
                resources = await self._mcp_client.list_resources()
                resources_count = len(resources)
            except UpstreamTransientError as exc:
                logger.warning("mcp_resources_list_failed", session_id=task.session_id, error=str(exc))

            try:
                template_count = len(await self._mcp_client.list_resource_templates())
            except UpstreamTransientError as exc:
                logger.warning("mcp_resource_templates_list_failed", session_id=task.session_id, error=str(exc))

            try:
                await self._mcp_client.ping()
            except UpstreamTransientError as exc:
                logger.warning("mcp_ping_failed", session_id=task.session_id, error=str(exc))

            await self._emit(
                task,
                "action",
                {
                    "text": (
                        f"MCP 서버 `{server_name}`를 연결했고 프로토콜 `{protocol_version}`로 합의했어요. "
                        f"도구={tools_count}개, 프롬프트={prompts_count}개, 리소스={resources_count}개, "
                        f"리소스 템플릿={template_count}개를 확인했어요."
                    )
                },
            )

        enforce_provider_and_model(
            provider=task.provider,
            model=effective_model,
            constraints=policy_constraints,
            available_skills=set(policy_snapshot.available_skills),
        )

        provider_adapter = self._provider_manager.resolve(task.provider)
        next_tool_results: list[ProviderToolResult] = []

        for round_index in range(MAX_TOOL_CALL_ROUNDS):
            provider_request = ProviderRequest(
                session_id=task.session_id,
                user_id=task.user_id,
                provider=task.provider,
                model=effective_model,
                text=effective_text,
                attachments=task.attachments,
                mcp_enabled=effective_mcp_enabled,
                mcp_profile_name=effective_mcp_profile_name,
                rules_summary=policy_snapshot.rules_summary,
                agents_summary=policy_snapshot.agents_summary,
                skills_summary=policy_snapshot.skills_summary,
                claude_memory_summary=effective_claude_memory_summary,
                mcp_tools=mcp_tools,
                tool_results=next_tool_results,
                tool_call_round=round_index,
            )
            provider_response = await provider_adapter.generate(provider_request)

            await self._emit(task, "decision_summary", {"text": provider_response.decision_summary})
            if provider_response.output_text:
                await self._emit(task, "response_delta", {"text": provider_response.output_text})

            if not provider_response.tool_requests:
                await self._emit(task, "final", {"text": "작업을 완료했어요."})
                return

            if not effective_mcp_enabled:
                await self._emit(
                    task,
                    "action",
                    {"text": "프로바이더가 도구 호출을 요청했지만 MCP가 비활성 상태라 도구를 실행하지 않았어요."},
                )
                await self._emit(task, "final", {"text": "도구 요청을 처리하지 못해 작업을 종료했어요."})
                return

            if self._mcp_client is None:
                await self._emit(
                    task,
                    "action",
                    {"text": "프로바이더가 도구 호출을 요청했지만 MCP 클라이언트가 없어 실행하지 못했어요."},
                )
                await self._emit(task, "final", {"text": "도구 요청을 처리하지 못해 작업을 종료했어요."})
                return

            next_tool_results = []
            for tool_request in provider_response.tool_requests:
                try:
                    tool_result = await self._mcp_client.call_tool(
                        name=tool_request.name,
                        arguments=tool_request.arguments,
                    )
                    next_tool_results.append(
                        ProviderToolResult(
                            name=tool_request.name,
                            call_id=tool_request.call_id,
                            ok=True,
                            result=tool_result,
                        )
                    )
                    await self._emit(
                        task,
                        "action",
                        {"text": f"MCP 도구 `{tool_request.name}` 호출을 성공적으로 완료했어요."},
                    )
                except Exception as exc:
                    error_text = str(exc) or "알 수 없는 오류"
                    next_tool_results.append(
                        ProviderToolResult(
                            name=tool_request.name,
                            call_id=tool_request.call_id,
                            ok=False,
                            error=error_text,
                        )
                    )
                    await self._emit(
                        task,
                        "action",
                        {"text": f"MCP 도구 `{tool_request.name}` 호출이 실패했어요: {error_text}"},
                    )

        await self._emit(
            task,
            "final",
            {"text": f"도구 호출 라운드가 {MAX_TOOL_CALL_ROUNDS}회를 넘어 작업을 종료했어요."},
        )

    async def _emit(self, task: TurnTask, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "session_id": task.session_id,
            "turn_id": task.turn_id,
            "type": event_type,
            "payload": payload,
        }
        await self._sink.publish(event)
