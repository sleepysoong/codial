from __future__ import annotations

from dataclasses import dataclass
from typing import Any

JSONRPC_VERSION = "2.0"


@dataclass(slots=True)
class McpTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]


@dataclass(slots=True)
class McpInitializeResult:
    server_name: str | None
    server_version: str | None
