from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def _bootstrap_paths() -> Path:
    service_root = Path(__file__).resolve().parents[1]
    repo_root = service_root.parent
    os.chdir(service_root)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return service_root


def _run(*, reload_enabled: bool) -> None:
    _bootstrap_paths()
    host = os.getenv("CORE_HOST", "0.0.0.0")
    port = int(os.getenv("CORE_PORT", "8081"))
    uvicorn.run(
        "codial_service.app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )


def main() -> None:
    _run(reload_enabled=False)


def main_dev() -> None:
    _run(reload_enabled=True)
