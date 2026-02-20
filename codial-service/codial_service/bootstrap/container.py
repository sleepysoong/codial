from __future__ import annotations

from dataclasses import dataclass

from codial_service.app.attachment_ingestor import AttachmentIngestor
from codial_service.app.codial_rules import CodialRuleStore
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
from codial_service.app.settings import Settings
from codial_service.app.store import InMemorySessionStore
from codial_service.app.tools.defaults import build_default_tool_registry
from codial_service.modules.sessions.service import SessionService
from codial_service.modules.turns.service import TurnsService
from codial_service.modules.turns.worker import TurnWorkerPool


@dataclass(slots=True)
class RuntimeComponents:
    sink: GatewayEventSink
    attachment_ingestor: AttachmentIngestor
    mcp_client: McpClient | None
    store: InMemorySessionStore
    policy_loader: PolicyLoader
    codial_rule_store: CodialRuleStore
    session_service: SessionService
    turns_service: TurnsService
    worker_pool: TurnWorkerPool


async def build_runtime_components(settings: Settings) -> RuntimeComponents:
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

    provider_adapters = {
        adapter.name: adapter
        for adapter in build_provider_adapters(
            settings,
            enabled_providers=enabled_providers,
            copilot_token_override=copilot_token_override,
        )
    }

    attachment_ingestor = AttachmentIngestor(
        download_enabled=settings.attachment_download_enabled,
        max_bytes=settings.attachment_download_max_bytes,
        storage_dir=settings.attachment_storage_dir,
        timeout_seconds=settings.request_timeout_seconds,
    )

    mcp_client: McpClient | None = None
    if settings.mcp_server_url:
        mcp_client = McpClient(
            server_url=settings.mcp_server_url,
            token=settings.mcp_server_token,
            timeout_seconds=settings.mcp_request_timeout_seconds,
        )

    tool_registry = build_default_tool_registry(workspace_root=settings.workspace_root)
    store = InMemorySessionStore()
    policy_loader = PolicyLoader(workspace_root=settings.workspace_root)
    codial_rule_store = CodialRuleStore(workspace_root=settings.workspace_root)
    session_service = SessionService(
        store=store,
        policy_loader=policy_loader,
        enabled_provider_names=enabled_providers,
        workspace_root=settings.workspace_root,
    )

    worker_pool = TurnWorkerPool(
        sink=sink,
        attachment_ingestor=attachment_ingestor,
        mcp_client=mcp_client,
        provider_adapters=provider_adapters,
        policy_loader=policy_loader,
        tool_registry=tool_registry,
        worker_count=settings.turn_worker_count,
        workspace_root=settings.workspace_root,
    )
    turns_service = TurnsService(store=store, worker_pool=worker_pool)

    return RuntimeComponents(
        sink=sink,
        attachment_ingestor=attachment_ingestor,
        mcp_client=mcp_client,
        store=store,
        policy_loader=policy_loader,
        codial_rule_store=codial_rule_store,
        session_service=session_service,
        turns_service=turns_service,
        worker_pool=worker_pool,
    )
