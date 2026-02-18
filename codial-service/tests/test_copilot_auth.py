from __future__ import annotations

from pathlib import Path

import pytest
from codial_service.app.providers.copilot_auth import (
    CopilotAuthBootstrapper,
    CopilotAuthSettings,
)

from libs.common.errors import ConfigurationError


class _StubBootstrapper(CopilotAuthBootstrapper):
    def __init__(self, settings: CopilotAuthSettings, login_token: str) -> None:
        super().__init__(settings)
        self.login_token = login_token
        self.login_called = 0

    async def _request_login_token(self) -> str:
        self.login_called += 1
        return self.login_token


def _build_settings(tmp_path: Path, *, bridge_token: str = "", auto_login_enabled: bool = True) -> CopilotAuthSettings:
    return CopilotAuthSettings(
        bridge_base_url="http://bridge.local",
        bridge_token=bridge_token,
        timeout_seconds=3.0,
        cache_path=".runtime/copilot-auth.json",
        workspace_root=str(tmp_path),
        auto_login_enabled=auto_login_enabled,
        login_endpoint="/v1/auth/login",
    )


@pytest.mark.asyncio
async def test_bootstrapper_prefers_env_token_and_writes_cache(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, bridge_token="env-token")
    bootstrapper = _StubBootstrapper(settings, login_token="login-token")

    token = await bootstrapper.ensure_token()
    assert token == "env-token"
    assert bootstrapper.login_called == 0


@pytest.mark.asyncio
async def test_bootstrapper_uses_cache_before_login(tmp_path: Path) -> None:
    cache_path = tmp_path / ".runtime" / "copilot-auth.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text('{"token":"cached-token"}', encoding="utf-8")

    settings = _build_settings(tmp_path)
    bootstrapper = _StubBootstrapper(settings, login_token="login-token")

    token = await bootstrapper.ensure_token()
    assert token == "cached-token"
    assert bootstrapper.login_called == 0


@pytest.mark.asyncio
async def test_bootstrapper_auto_login_when_cache_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    bootstrapper = _StubBootstrapper(settings, login_token="login-token")

    token = await bootstrapper.ensure_token()
    assert token == "login-token"
    assert bootstrapper.login_called == 1


@pytest.mark.asyncio
async def test_bootstrapper_raises_when_no_token_and_auto_login_disabled(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, auto_login_enabled=False)
    bootstrapper = _StubBootstrapper(settings, login_token="login-token")

    with pytest.raises(ConfigurationError):
        await bootstrapper.ensure_token()
