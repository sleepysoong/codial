from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from libs.common.errors import ConfigurationError, UpstreamTransientError
from libs.common.logging import get_logger

logger = get_logger("codial_service.providers.copilot_auth")


@dataclass(slots=True)
class CopilotAuthSettings:
    bridge_base_url: str
    bridge_token: str
    timeout_seconds: float
    cache_path: str
    workspace_root: str
    auto_login_enabled: bool
    login_endpoint: str


class CopilotAuthBootstrapper:
    def __init__(self, settings: CopilotAuthSettings) -> None:
        self._settings = settings

    async def ensure_token(self) -> str:
        if self._settings.bridge_token:
            self._write_cached_token(self._settings.bridge_token)
            logger.info("copilot_auth_ready", source="env", cache_path=str(self._cache_file_path()))
            return self._settings.bridge_token

        cached_token = self._read_cached_token()
        if cached_token:
            logger.info("copilot_auth_ready", source="cache", cache_path=str(self._cache_file_path()))
            return cached_token

        if not self._settings.auto_login_enabled:
            raise ConfigurationError("Copilot 로그인 토큰이 없고 자동 로그인이 비활성화되어 있어요.")

        token = await self._request_login_token()
        self._write_cached_token(token)
        logger.info("copilot_auth_ready", source="login", cache_path=str(self._cache_file_path()))
        return token

    def _cache_file_path(self) -> Path:
        candidate = Path(self._settings.cache_path).expanduser()
        if candidate.is_absolute():
            return candidate
        return (Path(self._settings.workspace_root).expanduser() / candidate).resolve()

    def _read_cached_token(self) -> str | None:
        cache_path = self._cache_file_path()
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        token_value = payload.get("token")
        if isinstance(token_value, str) and token_value:
            return token_value
        return None

    def _write_cached_token(self, token: str) -> None:
        cache_path = self._cache_file_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"token": token}
        cache_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")

    async def _request_login_token(self) -> str:
        base_url = self._settings.bridge_base_url.rstrip("/")
        if not base_url:
            raise ConfigurationError("Copilot 브리지 주소가 설정되지 않아 자동 로그인을 진행할 수 없어요.")

        endpoint = self._settings.login_endpoint.strip()
        login_path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        login_url = f"{base_url}{login_path}"

        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self._settings.timeout_seconds) as client:
                response = await client.post(login_url, json={}, headers=headers)
        except httpx.TimeoutException as exc:
            raise UpstreamTransientError("Copilot 자동 로그인 요청이 시간 초과됐어요.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamTransientError("Copilot 자동 로그인 요청 중 네트워크 오류가 발생했어요.") from exc

        if response.status_code >= 500:
            raise UpstreamTransientError("Copilot 자동 로그인 서버 오류가 발생했어요.")
        if response.status_code >= 400:
            raise ConfigurationError(
                f"Copilot 자동 로그인 요청이 거부됐어요. status={response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ConfigurationError("Copilot 자동 로그인 응답이 JSON 형식이 아니에요.") from exc
        token = _extract_token(body)
        if not token:
            raise ConfigurationError("Copilot 자동 로그인 응답에서 토큰을 찾지 못했어요.")
        return token


def _extract_token(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None

    for key in ("token", "access_token", "bearer_token", "api_key"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value

    nested = body.get("data")
    if isinstance(nested, dict):
        return _extract_token(nested)

    return None
