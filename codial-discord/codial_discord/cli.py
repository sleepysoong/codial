from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def _bootstrap_paths() -> Path:
    discord_root = Path(__file__).resolve().parents[1]
    repo_root = discord_root.parent
    os.chdir(discord_root)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return discord_root


def _run(*, reload_enabled: bool) -> None:
    _bootstrap_paths()
    host = os.getenv("DGW_HOST", "0.0.0.0")
    port = int(os.getenv("DGW_PORT", "8080"))
    uvicorn.run(
        "codial_discord.app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )


def main() -> None:
    _run(reload_enabled=False)


def main_dev() -> None:
    _run(reload_enabled=True)
