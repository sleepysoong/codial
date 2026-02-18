from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORE_", extra="ignore")

    service_name: str = "agent-core-api"
    host: str = "0.0.0.0"
    port: int = 8081
    api_token: str = "dev-core-token"
    gateway_base_url: str = "http://localhost:8080"
    gateway_internal_token: str = "dev-internal-token"
    request_timeout_seconds: float = 10.0
    turn_worker_count: int = 2
    openai_api_key: str = ""
    openai_request_timeout_seconds: float = 45.0
    workspace_root: str = "."


settings = Settings()
