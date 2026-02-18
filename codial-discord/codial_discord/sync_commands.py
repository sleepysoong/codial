from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from codial_discord.app.discord_api_client import DiscordApiClient
from codial_discord.app.settings import settings
from codial_discord.command_specs import build_application_commands
from libs.common.errors import ConfigurationError
from libs.common.logging import configure_logging, get_logger

logger = get_logger("codial_discord.sync_commands")


def _bootstrap_paths() -> None:
    discord_root = Path(__file__).resolve().parents[1]
    repo_root = discord_root.parent
    os.chdir(discord_root)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


async def _sync_commands() -> None:
    application_id = settings.discord_application_id.strip()
    if not application_id:
        raise ConfigurationError("DGW_DISCORD_APPLICATION_ID가 비어 있어서 커맨드를 동기화할 수 없어요.")

    client = DiscordApiClient(
        bot_token=settings.discord_bot_token,
        timeout_seconds=settings.request_timeout_seconds,
    )
    commands = build_application_commands()
    synced = await client.bulk_overwrite_application_commands(
        application_id=application_id,
        commands=commands,
        guild_id=settings.discord_command_guild_id,
    )
    names = [item.get("name", "") for item in synced if isinstance(item, dict)]
    scope = f"guild:{settings.discord_command_guild_id}" if settings.discord_command_guild_id else "global"
    logger.info("discord_commands_synced", scope=scope, count=len(synced), names=names)


def main() -> None:
    _bootstrap_paths()
    configure_logging()
    asyncio.run(_sync_commands())
