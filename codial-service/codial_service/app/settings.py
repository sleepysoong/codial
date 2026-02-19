from __future__ import annotations

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CORE_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    service_name: str = "agent-core-api"
    host: str = "0.0.0.0"
    port: int = 8081
    api_token: str = "dev-core-token"
    gateway_base_url: str = "http://localhost:8080"
    gateway_internal_token: str = "dev-internal-token"
    request_timeout_seconds: float = 10.0
    turn_worker_count: int = 2
    default_provider_name: str = "github-copilot-sdk"
    # CSV 문자열 또는 리스트 모두 허용해요 (#18)
    enabled_provider_names: list[str] = Field(default_factory=lambda: ["github-copilot-sdk"])
    copilot_bridge_base_url: str = ""
    copilot_bridge_token: str = ""
    provider_bridge_timeout_seconds: float = 30.0
    copilot_auto_login_enabled: bool = True
    copilot_auth_cache_path: str = ".runtime/copilot-auth.json"
    copilot_login_endpoint: str = "/v1/auth/login"
    mcp_server_url: str = ""
    mcp_server_token: str = ""
    mcp_request_timeout_seconds: float = 15.0
    attachment_download_enabled: bool = False
    attachment_download_max_bytes: int = 10_000_000
    attachment_storage_dir: str = ".runtime/attachments"
    workspace_root: str = "."

    @field_validator("enabled_provider_names", mode="before")
    @classmethod
    def _parse_provider_names(cls, value: object) -> list[str]:
        """환경변수에서 CSV 문자열로 들어온 경우 리스트로 변환해요."""
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return parts if parts else ["github-copilot-sdk"]
        return value  # type: ignore[return-value]

    @model_validator(mode="after")
    def _warn_insecure_tokens(self) -> "Settings":
        """개발용 기본 토큰이 프로덕션에서 그대로 쓰이지 않도록 경고를 남겨요. (#20)"""
        import logging
        _log = logging.getLogger("codial_service.settings")
        _INSECURE = {"dev-core-token", "dev-internal-token", ""}
        if self.api_token in _INSECURE:
            _log.warning("CORE_API_TOKEN이 기본값이에요. 프로덕션 환경에서는 반드시 교체해야 해요.")
        if self.gateway_internal_token in _INSECURE:
            _log.warning("CORE_GATEWAY_INTERNAL_TOKEN이 기본값이에요. 프로덕션 환경에서는 반드시 교체해야 해요.")
        return self


settings = Settings()
