from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(slots=True)
class ErrorEnvelope:
    error_code: str
    message: str
    trace_id: str
    retryable: bool


class DomainError(Exception):
    def __init__(self, error_code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.retryable = retryable


class AuthenticationError(DomainError):
    def __init__(self, message: str = "인증에 실패했어요.") -> None:
        super().__init__("AUTH_FAILED", message, retryable=False)


class ValidationError(DomainError):
    def __init__(self, message: str = "검증에 실패했어요.") -> None:
        super().__init__("VALIDATION_FAILED", message, retryable=False)


class UpstreamTransientError(DomainError):
    def __init__(self, message: str = "외부 시스템에 일시적인 문제가 발생했어요.") -> None:
        super().__init__("UPSTREAM_TRANSIENT", message, retryable=True)


class RateLimitError(DomainError):
    def __init__(self, message: str = "요청 제한을 초과했어요.") -> None:
        super().__init__("RATE_LIMITED", message, retryable=True)


class TimeoutError(DomainError):
    def __init__(self, message: str = "작업 시간이 초과됐어요.") -> None:
        super().__init__("TIMEOUT", message, retryable=True)


class NotFoundError(DomainError):
    def __init__(self, message: str = "대상을 찾지 못했어요.") -> None:
        super().__init__("NOT_FOUND", message, retryable=False)


class ConfigurationError(DomainError):
    def __init__(self, message: str = "설정이 올바르지 않아요.") -> None:
        super().__init__("CONFIGURATION_ERROR", message, retryable=False)


def build_error_envelope(error_code: str, message: str, retryable: bool) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code=error_code,
        message=message,
        trace_id=str(uuid.uuid4()),
        retryable=retryable,
    )
