from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from libs.common.http_handlers import register_exception_handlers
from libs.common.logging import configure_logging
from services.agent_core_api.app.event_sink import GatewayEventSink
from services.agent_core_api.app.policy_loader import PolicyLoader
from services.agent_core_api.app.providers.manager import ProviderManager
from services.agent_core_api.app.providers.openai_adapter import OpenAiProviderAdapter
from services.agent_core_api.app.providers.placeholder_adapter import PlaceholderProviderAdapter
from services.agent_core_api.app.routes import router
from services.agent_core_api.app.settings import settings
from services.agent_core_api.app.turn_worker import TurnWorkerPool

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    sink = GatewayEventSink(
        base_url=settings.gateway_base_url,
        token=settings.gateway_internal_token,
        timeout_seconds=settings.request_timeout_seconds,
    )
    provider_manager = ProviderManager(
        adapters=[
            OpenAiProviderAdapter(
                api_key=settings.openai_api_key,
                timeout_seconds=settings.openai_request_timeout_seconds,
            ),
            PlaceholderProviderAdapter(
                name="openai-codex",
                description="Codex CLI 브리지 연동은 다음 단계에서 연결해요.",
            ),
            PlaceholderProviderAdapter(
                name="github-copilot-sdk",
                description="GitHub Copilot SDK 연동은 다음 단계에서 연결해요.",
            ),
        ]
    )
    policy_loader = PolicyLoader(workspace_root=settings.workspace_root)
    worker_pool = TurnWorkerPool(
        sink=sink,
        provider_manager=provider_manager,
        policy_loader=policy_loader,
        worker_count=settings.turn_worker_count,
    )
    await worker_pool.start()
    app.state.turn_worker_pool = worker_pool
    try:
        yield
    finally:
        await worker_pool.stop()


app = FastAPI(title=settings.service_name, lifespan=lifespan)
app.include_router(router)
register_exception_handlers(app, "agent_core_api.errors")
