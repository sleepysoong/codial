from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from libs.common.errors import DomainError
from libs.common.logging import get_logger


def register_exception_handlers(app: FastAPI, logger_name: str) -> None:
    logger = get_logger(logger_name)

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        trace_id = str(uuid.uuid4())
        logger.warning(
            "domain_error",
            path=request.url.path,
            method=request.method,
            trace_id=trace_id,
            error_code=exc.error_code,
            message=exc.message,
            retryable=exc.retryable,
        )
        return JSONResponse(
            status_code=400,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "trace_id": trace_id,
                "retryable": exc.retryable,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        trace_id = str(uuid.uuid4())
        logger.exception(
            "unhandled_error",
            path=request.url.path,
            method=request.method,
            trace_id=trace_id,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "예상하지 못한 내부 오류가 발생했어요.",
                "trace_id": trace_id,
                "retryable": True,
            },
        )
