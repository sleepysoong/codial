from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from codial_service.app.attachment_ingestor import AttachmentIngestor
from codial_service.app.event_sink import GatewayEventSink
from codial_service.app.mcp_client import McpClient
from codial_service.app.policy_loader import PolicyLoader
from codial_service.app.providers.catalog import (
    build_provider_adapters,
    get_enabled_provider_names,
)
from codial_service.app.providers.copilot_auth import (
    CopilotAuthBootstrapper,
    CopilotAuthSettings,
)
from codial_service.app.providers.manager import ProviderManager
from codial_service.app.routes import router
from codial_service.app.settings import settings
from codial_service.app.turn_worker import TurnWorkerPool
from libs.common.http_handlers import register_exception_handlers
from libs.common.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    sink = GatewayEventSink(
        base_url=settings.gateway_base_url,
        token=settings.gateway_internal_token,
        timeout_seconds=settings.request_timeout_seconds,
    )

    enabled_providers = get_enabled_provider_names(
        settings.enabled_provider_names,
        fallback_default=settings.default_provider_name,
    )
    copilot_token_override: str | None = None
    if "github-copilot-sdk" in enabled_providers:
        bootstrapper = CopilotAuthBootstrapper(
            CopilotAuthSettings(
                bridge_base_url=settings.copilot_bridge_base_url,
                bridge_token=settings.copilot_bridge_token,
                timeout_seconds=settings.provider_bridge_timeout_seconds,
                cache_path=settings.copilot_auth_cache_path,
                workspace_root=settings.workspace_root,
                auto_login_enabled=settings.copilot_auto_login_enabled,
                login_endpoint=settings.copilot_login_endpoint,
            )
        )
        copilot_token_override = await bootstrapper.ensure_token()

    provider_manager = ProviderManager(
        adapters=build_provider_adapters(
            settings,
            enabled_providers=enabled_providers,
            copilot_token_override=copilot_token_override,
        )
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
        workspace_root=settings.workspace_root,
    )
    await worker_pool.start()
    app.state.turn_worker_pool = worker_pool
    try:
        yield
    finally:
        await worker_pool.stop()


app = FastAPI(title=settings.service_name, lifespan=lifespan)
app.include_router(router)
register_exception_handlers(app, "codial_service.errors")
