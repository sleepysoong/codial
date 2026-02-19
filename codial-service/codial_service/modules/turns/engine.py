from __future__ import annotations

from pathlib import Path
from typing import Any

from codial_service.app.policy_engine import (
    enforce_provider_and_model,
    parse_policy_constraints,
)
from codial_service.app.policy_loader import PolicyLoader, PolicySnapshot
from codial_service.app.providers.base import (
    ProviderAdapter,
    ProviderRequest,
    ProviderToolRequest,
    ProviderToolResult,
    ProviderToolSpec,
)
from codial_service.app.subagent_spec import SubagentSpec, default_subagent_search_paths, discover_subagents
from codial_service.app.tools.registry import ToolRegistry
from codial_service.app.turn_events import TurnEventType
from codial_service.modules.turns.contracts import (
    AttachmentIngestorProtocol,
    EventSinkProtocol,
    McpClientProtocol,
    TurnTask,
)
from libs.common.errors import UpstreamTransientError
from libs.common.logging import get_logger

logger = get_logger("codial_service.turn_engine")


class TurnEngine:
    def __init__(
        self,
        *,
        sink: EventSinkProtocol,
        attachment_ingestor: AttachmentIngestorProtocol,
        mcp_client: McpClientProtocol | None,
        provider_adapters: dict[str, ProviderAdapter],
        policy_loader: PolicyLoader,
        tool_registry: ToolRegistry,
        workspace_root: str,
    ) -> None:
        self._sink = sink
        self._attachment_ingestor = attachment_ingestor
        self._mcp_client = mcp_client
        self._provider_adapters = provider_adapters
        self._policy_loader = policy_loader
        self._tool_registry = tool_registry
        self._workspace_root = Path(workspace_root)

    async def process(self, task: TurnTask) -> None:
        policy_snapshot = self._policy_loader.load()
        policy_constraints = parse_policy_constraints(policy_snapshot.rules_text)
        effective_text, effective_model, effective_mcp_enabled, effective_mcp_profile_name, effective_memory = (
            await self._apply_plan_and_subagent(task, policy_snapshot)
        )

        ingest_summary = await self._ingest_attachments(task)
        await self._emit(task, TurnEventType.ACTION, {"text": ingest_summary})

        builtin_tool_names, all_tool_specs = self._collect_builtin_tools()
        all_tool_specs = await self._collect_mcp_tools(task, effective_mcp_enabled, all_tool_specs, builtin_tool_names)

        enforce_provider_and_model(
            provider=task.provider,
            model=effective_model,
            constraints=policy_constraints,
            available_skills=set(policy_snapshot.available_skills),
        )

        provider_adapter = self._provider_adapters.get(task.provider)
        if provider_adapter is None:
            supported = ", ".join(sorted(self._provider_adapters.keys()))
            raise ValueError(f"지원하지 않는 프로바이더예요: `{task.provider}`. 지원 목록: {supported}")

        await self._run_provider_loop(
            task=task,
            provider_adapter=provider_adapter,
            effective_text=effective_text,
            effective_model=effective_model,
            effective_mcp_enabled=effective_mcp_enabled,
            effective_mcp_profile_name=effective_mcp_profile_name,
            effective_memory=effective_memory,
            policy_snapshot=policy_snapshot,
            all_tool_specs=all_tool_specs,
            builtin_tool_names=builtin_tool_names,
        )

    async def emit(self, task: TurnTask, event_type: str, payload: dict[str, Any]) -> None:
        await self._emit(task, event_type, payload)

    async def _apply_plan_and_subagent(
        self,
        task: TurnTask,
        policy_snapshot: PolicySnapshot,
    ) -> tuple[str, str, bool, str | None, str]:
        attachment_count = len(task.attachments)
        effective_text = task.text
        effective_model = task.model
        effective_mcp_enabled = task.mcp_enabled
        effective_mcp_profile_name = task.mcp_profile_name
        effective_memory = policy_snapshot.system_memory_summary

        await self._emit(
            task,
            TurnEventType.PLAN,
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
            TurnEventType.ACTION,
            {
                "text": (
                    "정책 파일을 로드했어요. "
                    f"CLAUDE.md=`{policy_snapshot.system_memory_summary}`, "
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
                    TurnEventType.ACTION,
                    {
                        "text": (
                            f"서브에이전트 `{task.subagent_name}`를 찾지 못했어요. "
                            "기본 세션 설정으로 계속 진행해요."
                        )
                    },
                )
            else:
                effective_text, effective_model, effective_mcp_enabled, effective_mcp_profile_name, effective_memory = (
                    self._apply_subagent(
                        subagent,
                        effective_text,
                        effective_model,
                        effective_mcp_enabled,
                        effective_mcp_profile_name,
                        effective_memory,
                    )
                )
                mcp_state = "활성" if effective_mcp_enabled else "비활성"
                await self._emit(
                    task,
                    TurnEventType.ACTION,
                    {
                        "text": (
                            f"서브에이전트 `{subagent.name}`를 적용했어요. "
                            f"적용 모델=`{effective_model}`, MCP=`{mcp_state}`"
                        )
                    },
                )

        return effective_text, effective_model, effective_mcp_enabled, effective_mcp_profile_name, effective_memory

    def _apply_subagent(
        self,
        subagent: SubagentSpec,
        text: str,
        model: str,
        mcp_enabled: bool,
        mcp_profile_name: str | None,
        memory: str,
    ) -> tuple[str, str, bool, str | None, str]:
        if subagent.model != "inherit":
            model = subagent.model
        if subagent.prompt:
            text = f"{subagent.prompt}\n\n사용자 요청:\n{text}" if text else subagent.prompt
        if subagent.mcp_servers:
            mcp_enabled = True
            if not mcp_profile_name:
                mcp_profile_name = subagent.mcp_servers[0]
        if subagent.memory:
            memory = f"{memory}, subagent-memory={subagent.memory}"
        return text, model, mcp_enabled, mcp_profile_name, memory

    async def _ingest_attachments(self, task: TurnTask) -> str:
        result = await self._attachment_ingestor.ingest(
            session_id=task.session_id,
            turn_id=task.turn_id,
            attachments=task.attachments,
        )
        return result.summary

    def _collect_builtin_tools(self) -> tuple[set[str], list[ProviderToolSpec]]:
        builtin_tool_names: set[str] = set()
        all_tool_specs: list[ProviderToolSpec] = []
        builtin_specs = self._tool_registry.to_provider_specs()
        for spec in builtin_specs:
            builtin_tool_names.add(spec.name)
            all_tool_specs.append(spec)
        return builtin_tool_names, all_tool_specs

    async def _collect_mcp_tools(
        self,
        task: TurnTask,
        effective_mcp_enabled: bool,
        all_tool_specs: list[ProviderToolSpec],
        builtin_tool_names: set[str],
    ) -> list[ProviderToolSpec]:
        await self._emit(
            task,
            TurnEventType.ACTION,
            {"text": f"내장 도구 {len(builtin_tool_names)}개를 등록했어요: {', '.join(sorted(builtin_tool_names))}"},
        )

        if not (effective_mcp_enabled and self._mcp_client is not None):
            return all_tool_specs

        initialize_result = await self._mcp_client.ensure_initialized(
            client_name="codial-core",
            client_version="0.1.0",
        )
        server_name = initialize_result.server_name or "알 수 없는 서버"
        protocol_version = initialize_result.protocol_version or "미확인"

        try:
            raw_tools = await self._mcp_client.list_tools()
        except UpstreamTransientError as exc:
            logger.warning("mcp_tools_list_failed", session_id=task.session_id, error=str(exc))
            await self._emit(
                task,
                TurnEventType.ACTION,
                {
                    "text": (
                        f"MCP 서버 `{server_name}` 연결은 완료했지만 도구 목록을 가져오지 못했어요. "
                        "이번 턴은 내장 도구만 사용해요."
                    )
                },
            )
            return all_tool_specs

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

        await self._emit(
            task,
            TurnEventType.ACTION,
            {
                "text": (
                    f"MCP 서버 `{server_name}`를 연결했고 프로토콜 `{protocol_version}`로 합의했어요. "
                    f"도구={len(mcp_tools)}개를 확인했어요."
                )
            },
        )

        for mcp_spec in mcp_tools:
            if mcp_spec.name not in builtin_tool_names:
                all_tool_specs.append(mcp_spec)

        return all_tool_specs

    async def _run_provider_loop(
        self,
        *,
        task: TurnTask,
        provider_adapter: ProviderAdapter,
        effective_text: str,
        effective_model: str,
        effective_mcp_enabled: bool,
        effective_mcp_profile_name: str | None,
        effective_memory: str,
        policy_snapshot: PolicySnapshot,
        all_tool_specs: list[ProviderToolSpec],
        builtin_tool_names: set[str],
    ) -> None:
        next_tool_results: list[ProviderToolResult] = []
        round_index = 0

        while True:
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
                system_memory_summary=effective_memory,
                tool_specs=all_tool_specs,
                tool_results=next_tool_results,
                tool_call_round=round_index,
            )
            provider_response = await provider_adapter.generate(provider_request)

            await self._emit(task, TurnEventType.DECISION_SUMMARY, {"text": provider_response.decision_summary})
            if provider_response.output_text:
                await self._emit(task, TurnEventType.RESPONSE_DELTA, {"text": provider_response.output_text})

            if not provider_response.tool_requests:
                await self._emit(task, TurnEventType.FINAL, {"text": "작업을 완료했어요."})
                return

            next_tool_results = await self._dispatch_tool_calls(
                task=task,
                tool_requests=provider_response.tool_requests,
                builtin_tool_names=builtin_tool_names,
                effective_mcp_enabled=effective_mcp_enabled,
            )
            round_index += 1

    async def _dispatch_tool_calls(
        self,
        *,
        task: TurnTask,
        tool_requests: list[ProviderToolRequest],
        builtin_tool_names: set[str],
        effective_mcp_enabled: bool,
    ) -> list[ProviderToolResult]:
        results: list[ProviderToolResult] = []
        for tool_request in tool_requests:
            if tool_request.name in builtin_tool_names:
                result = await self._call_builtin_tool(task, tool_request)
            elif effective_mcp_enabled and self._mcp_client is not None:
                result = await self._call_mcp_tool(task, tool_request)
            else:
                result = ProviderToolResult(
                    name=tool_request.name,
                    call_id=tool_request.call_id,
                    ok=False,
                    error=f"도구 `{tool_request.name}`을 실행할 수 없어요. 내장 도구가 아니고 MCP도 비활성 상태예요.",
                )
                await self._emit(
                    task,
                    TurnEventType.ACTION,
                    {"text": f"도구 `{tool_request.name}`을 실행할 수 없어요 (미등록 도구, MCP 비활성)."},
                )
            results.append(result)
        return results

    async def _call_builtin_tool(
        self,
        task: TurnTask,
        tool_request: ProviderToolRequest,
    ) -> ProviderToolResult:
        try:
            builtin_result = await self._tool_registry.call(tool_request.name, tool_request.arguments)
            status_text = "성공" if builtin_result.ok else "실패"
            await self._emit(
                task,
                TurnEventType.ACTION,
                {"text": f"내장 도구 `{tool_request.name}` 호출을 {status_text}했어요."},
            )
            return ProviderToolResult(
                name=tool_request.name,
                call_id=tool_request.call_id,
                ok=builtin_result.ok,
                result={"output": builtin_result.output, **builtin_result.metadata} if builtin_result.ok else None,
                error=builtin_result.error if not builtin_result.ok else None,
            )
        except Exception as exc:
            error_text = str(exc) or "알 수 없는 오류"
            await self._emit(
                task,
                TurnEventType.ACTION,
                {"text": f"내장 도구 `{tool_request.name}` 호출이 실패했어요: {error_text}"},
            )
            return ProviderToolResult(
                name=tool_request.name,
                call_id=tool_request.call_id,
                ok=False,
                error=error_text,
            )

    async def _call_mcp_tool(
        self,
        task: TurnTask,
        tool_request: ProviderToolRequest,
    ) -> ProviderToolResult:
        mcp_client = self._mcp_client
        if mcp_client is None:
            return ProviderToolResult(
                name=tool_request.name,
                call_id=tool_request.call_id,
                ok=False,
                error="MCP 클라이언트를 사용할 수 없어요.",
            )
        try:
            tool_result = await mcp_client.call_tool(
                name=tool_request.name,
                arguments=tool_request.arguments,
            )
            await self._emit(
                task,
                TurnEventType.ACTION,
                {"text": f"MCP 도구 `{tool_request.name}` 호출을 성공적으로 완료했어요."},
            )
            return ProviderToolResult(
                name=tool_request.name,
                call_id=tool_request.call_id,
                ok=True,
                result=tool_result,
            )
        except Exception as exc:
            error_text = str(exc) or "알 수 없는 오류"
            await self._emit(
                task,
                TurnEventType.ACTION,
                {"text": f"MCP 도구 `{tool_request.name}` 호출이 실패했어요: {error_text}"},
            )
            return ProviderToolResult(
                name=tool_request.name,
                call_id=tool_request.call_id,
                ok=False,
                error=error_text,
            )

    def _load_subagent_spec(self, subagent_name: str) -> SubagentSpec | None:
        specs = discover_subagents(default_subagent_search_paths(self._workspace_root))
        for spec in specs:
            if spec.name == subagent_name:
                return spec
        return None

    async def _emit(self, task: TurnTask, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "session_id": task.session_id,
            "turn_id": task.turn_id,
            "trace_id": task.trace_id,
            "type": event_type,
            "payload": payload,
        }
        await self._sink.publish(event)
