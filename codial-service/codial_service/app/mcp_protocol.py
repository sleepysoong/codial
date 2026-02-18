from __future__ import annotations

from dataclasses import dataclass
from typing import Any

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-11-25"


@dataclass(slots=True)
class McpTool:
    name: str
    title: str | None
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None


@dataclass(slots=True)
class McpPromptArgument:
    name: str
    description: str | None
    required: bool


@dataclass(slots=True)
class McpPrompt:
    name: str
    title: str | None
    description: str | None
    arguments: list[McpPromptArgument]


@dataclass(slots=True)
class McpResource:
    uri: str
    name: str
    title: str | None
    description: str | None
    mime_type: str | None


@dataclass(slots=True)
class McpResourceTemplate:
    uri_template: str
    name: str
    title: str | None
    description: str | None
    mime_type: str | None


@dataclass(slots=True)
class McpInitializeResult:
    server_name: str | None
    server_version: str | None
    protocol_version: str | None
    server_capabilities: dict[str, Any]
    instructions: str | None
    session_id: str | None
