from __future__ import annotations

from fastapi import FastAPI

from codial_service.app.settings import settings
from codial_service.bootstrap import create_lifespan
from codial_service.modules import build_api_router
from libs.common.http_handlers import register_exception_handlers
from libs.common.logging import configure_logging

configure_logging()

app = FastAPI(title=settings.service_name, lifespan=create_lifespan(settings))
app.include_router(build_api_router())
register_exception_handlers(app, "codial_service.errors")
