from __future__ import annotations

import asyncio
import contextlib
import uuid

from codial_service.app.models import TurnAttachment
from codial_service.app.policy_loader import PolicyLoader
from codial_service.app.providers.base import ProviderAdapter
from codial_service.app.tools.registry import ToolRegistry
from codial_service.app.turn_events import TurnEventType
from codial_service.modules.turns.contracts import (
    AttachmentIngestorProtocol,
    EventSinkProtocol,
    McpClientProtocol,
    TurnTask,
)
from codial_service.modules.turns.engine import TurnEngine
from libs.common.errors import DomainError
from libs.common.logging import get_logger

logger = get_logger("codial_service.turn_worker")


class TurnWorkerPool:
    def __init__(
        self,
        sink: EventSinkProtocol,
        attachment_ingestor: AttachmentIngestorProtocol,
        mcp_client: McpClientProtocol | None,
        provider_adapters: dict[str, ProviderAdapter],
        policy_loader: PolicyLoader,
        tool_registry: ToolRegistry,
        worker_count: int,
        workspace_root: str,
    ) -> None:
        self._worker_count = worker_count
        self._queue: asyncio.Queue[TurnTask] = asyncio.Queue(maxsize=1000)
        self._tasks: list[asyncio.Task[None]] = []
        self._closing = False
        self._engine = TurnEngine(
            sink=sink,
            attachment_ingestor=attachment_ingestor,
            mcp_client=mcp_client,
            provider_adapters=provider_adapters,
            policy_loader=policy_loader,
            tool_registry=tool_registry,
            workspace_root=workspace_root,
        )

    async def start(self) -> None:
        if self._tasks:
            return
        self._closing = False
        for idx in range(self._worker_count):
            self._tasks.append(asyncio.create_task(self._worker_loop(idx)))

    async def stop(self) -> None:
        """대기 중인 작업이 모두 처리될 때까지 기다린 후 워커를 종료해요."""
        self._closing = True
        try:
            await asyncio.wait_for(self._queue.join(), timeout=30.0)
        except TimeoutError:
            logger.warning("turn_worker_graceful_shutdown_timeout", pending=self._queue.qsize())
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
        trace_id: str | None = None,
    ) -> str:
        turn_id = str(uuid.uuid4())
        task = TurnTask(
            turn_id=turn_id,
            trace_id=trace_id or str(uuid.uuid4()),
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

    async def _worker_loop(self, worker_index: int) -> None:
        while not self._closing:
            task = await self._queue.get()
            try:
                await self._engine.process(task)
            except DomainError as exc:
                log_level = logger.warning if exc.retryable else logger.error
                log_level(
                    "turn_domain_error",
                    worker_index=worker_index,
                    trace_id=task.trace_id,
                    turn_id=task.turn_id,
                    error_code=exc.error_code,
                    retryable=exc.retryable,
                    error=str(exc),
                )
                await self._engine.emit(task, TurnEventType.ERROR, {"text": str(exc)})
            except Exception as exc:
                logger.exception(
                    "turn_unexpected_error",
                    worker_index=worker_index,
                    trace_id=task.trace_id,
                    turn_id=task.turn_id,
                    error=str(exc),
                )
                await self._engine.emit(
                    task,
                    TurnEventType.ERROR,
                    {"text": "요청 처리 중 예상치 못한 오류가 발생했어요."},
                )
            finally:
                self._queue.task_done()
