from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from codial_service.app.settings import Settings
from codial_service.bootstrap.container import build_runtime_components


def create_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = await build_runtime_components(settings)
        await runtime.worker_pool.start()

        app.state.store = runtime.store
        app.state.policy_loader = runtime.policy_loader
        app.state.codial_rule_store = runtime.codial_rule_store
        app.state.session_service = runtime.session_service
        app.state.turn_worker_pool = runtime.worker_pool
        app.state.settings = settings

        try:
            yield
        finally:
            await runtime.worker_pool.stop()
            await runtime.sink.aclose()
            await runtime.attachment_ingestor.aclose()
            if runtime.mcp_client is not None:
                await runtime.mcp_client.aclose()

    return lifespan
