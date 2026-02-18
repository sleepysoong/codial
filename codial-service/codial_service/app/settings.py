from __future__ import annotations

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
    enabled_provider_names: str = "github-copilot-sdk"
    openai_api_key: str = ""
    openai_request_timeout_seconds: float = 45.0
    codex_bridge_base_url: str = ""
    codex_bridge_token: str = ""
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


settings = Settings()
