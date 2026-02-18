from __future__ import annotations

from fastapi import FastAPI

from codial_discord.app.routes import router
from codial_discord.app.settings import settings
from libs.common.http_handlers import register_exception_handlers
from libs.common.logging import configure_logging

configure_logging()

app = FastAPI(title=settings.service_name)
app.include_router(router)
register_exception_handlers(app, "codial_discord.errors")
