from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from libs.common.http_handlers import register_exception_handlers
from libs.common.logging import configure_logging
from services.agent_core_api.app.attachment_ingestor import AttachmentIngestor
from services.agent_core_api.app.event_sink import GatewayEventSink
from services.agent_core_api.app.mcp_client import McpClient
from services.agent_core_api.app.policy_loader import PolicyLoader
from services.agent_core_api.app.providers.http_bridge_adapter import HttpBridgeProviderAdapter
from services.agent_core_api.app.providers.manager import ProviderManager
from services.agent_core_api.app.providers.openai_adapter import OpenAiProviderAdapter
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
            HttpBridgeProviderAdapter(
                name="openai-codex",
                base_url=settings.codex_bridge_base_url,
                token=settings.codex_bridge_token,
                timeout_seconds=settings.provider_bridge_timeout_seconds,
                provider_hint="Codex",
            ),
            HttpBridgeProviderAdapter(
                name="github-copilot-sdk",
                base_url=settings.copilot_bridge_base_url,
                token=settings.copilot_bridge_token,
                timeout_seconds=settings.provider_bridge_timeout_seconds,
                provider_hint="GitHub Copilot SDK",
            ),
        ]
    )
    policy_loader = PolicyLoader(workspace_root=settings.workspace_root)
    attachment_ingestor = AttachmentIngestor(
        download_enabled=settings.attachment_download_enabled,
        max_bytes=settings.attachment_download_max_bytes,
        storage_dir=settings.attachment_storage_dir,
        timeout_seconds=settings.request_timeout_seconds,
    )
    mcp_client = None
    if settings.mcp_server_url:
        mcp_client = McpClient(
            server_url=settings.mcp_server_url,
            token=settings.mcp_server_token,
            timeout_seconds=settings.mcp_request_timeout_seconds,
        )
    worker_pool = TurnWorkerPool(
        sink=sink,
        attachment_ingestor=attachment_ingestor,
        mcp_client=mcp_client,
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
