from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass
from typing import Any

from libs.common.logging import get_logger
from services.agent_core_api.app.attachment_ingestor import AttachmentIngestor
from services.agent_core_api.app.event_sink import GatewayEventSink
from services.agent_core_api.app.mcp_client import McpClient
from services.agent_core_api.app.models import TurnAttachment
from services.agent_core_api.app.policy_engine import (
    enforce_provider_and_model,
    parse_policy_constraints,
)
from services.agent_core_api.app.policy_loader import PolicyLoader
from services.agent_core_api.app.providers.base import ProviderRequest
from services.agent_core_api.app.providers.manager import ProviderManager

logger = get_logger("agent_core_api.turn_worker")


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


class TurnWorkerPool:
    def __init__(
        self,
        sink: GatewayEventSink,
        attachment_ingestor: AttachmentIngestor,
        mcp_client: McpClient | None,
        provider_manager: ProviderManager,
        policy_loader: PolicyLoader,
        worker_count: int,
    ) -> None:
        self._sink = sink
        self._attachment_ingestor = attachment_ingestor
        self._mcp_client = mcp_client
        self._provider_manager = provider_manager
        self._policy_loader = policy_loader
        self._worker_count = worker_count
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
        )
        await self._queue.put(task)
        return turn_id

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

        await self._emit(
            task,
            "plan",
            {
                "text": (
                    "요청을 분석하고 실행 계획을 준비하고 있어요. "
                    f"프로바이더=`{task.provider}`, 모델=`{task.model}`, 첨부파일={attachment_count}개"
                )
            },
        )
        await self._emit(
            task,
            "action",
            {
                "text": (
                    "정책 파일을 로드했어요. "
                    f"RULES=`{policy_snapshot.rules_summary}`, "
                    f"AGENTS=`{policy_snapshot.agents_summary}`, "
                    f"SKILLS=`{policy_snapshot.skills_summary}`"
                )
            },
        )

        ingest_result = await self._attachment_ingestor.ingest(
            session_id=task.session_id,
            turn_id=task.turn_id,
            attachments=task.attachments,
        )
        await self._emit(task, "action", {"text": ingest_result.summary})

        if task.mcp_enabled and self._mcp_client is not None:
            initialize_result = await self._mcp_client.initialize(
                client_name="codial-core",
                client_version="0.1.0",
            )
            tools = await self._mcp_client.list_tools()
            server_name = initialize_result.server_name or "알 수 없는 서버"
            await self._emit(
                task,
                "action",
                {
                    "text": (
                        f"MCP 서버 `{server_name}`를 연결했고 도구 {len(tools)}개를 확인했어요."
                    )
                },
            )

        enforce_provider_and_model(
            provider=task.provider,
            model=task.model,
            constraints=policy_constraints,
            available_skills=set(policy_snapshot.available_skills),
        )

        provider_adapter = self._provider_manager.resolve(task.provider)
        provider_request = ProviderRequest(
            session_id=task.session_id,
            user_id=task.user_id,
            provider=task.provider,
            model=task.model,
            text=task.text,
            attachments=task.attachments,
            mcp_enabled=task.mcp_enabled,
            mcp_profile_name=task.mcp_profile_name,
            rules_summary=policy_snapshot.rules_summary,
            agents_summary=policy_snapshot.agents_summary,
            skills_summary=policy_snapshot.skills_summary,
        )
        provider_response = await provider_adapter.generate(provider_request)

        await self._emit(task, "decision_summary", {"text": provider_response.decision_summary})
        await self._emit(task, "response_delta", {"text": provider_response.output_text})
        await self._emit(task, "final", {"text": "작업을 완료했어요."})

    async def _emit(self, task: TurnTask, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "session_id": task.session_id,
            "turn_id": task.turn_id,
            "type": event_type,
            "payload": payload,
        }
        await self._sink.publish(event)
