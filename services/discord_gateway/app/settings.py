from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DGW_", extra="ignore")

    service_name: str = "discord-gateway"
    host: str = "0.0.0.0"
    port: int = 8080

    discord_public_key: str = ""
    discord_bot_token: str = ""
    core_api_base_url: str = "http://localhost:8081"
    core_api_token: str = "dev-core-token"
    internal_event_token: str = "dev-internal-token"
    session_channel_prefix: str = "ai"
    session_category_id: str | None = None
    session_channel_topic_template: str = "AI coding session: {session_id}"

    request_timeout_seconds: float = 10.0
    max_concurrent_background_jobs: int = 20


settings = Settings()
