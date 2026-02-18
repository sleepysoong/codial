from __future__ import annotations

from fastapi import FastAPI

from libs.common.http_handlers import register_exception_handlers
from libs.common.logging import configure_logging
from services.discord_gateway.app.routes import router
from services.discord_gateway.app.settings import settings

configure_logging()

app = FastAPI(title=settings.service_name)
app.include_router(router)
register_exception_handlers(app, "discord_gateway.errors")
