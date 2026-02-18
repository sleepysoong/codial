from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    guild_id: str = Field(min_length=1)
    requester_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str


class BindChannelRequest(BaseModel):
    channel_id: str = Field(min_length=1)


class BindChannelResponse(BaseModel):
    session_id: str
    channel_id: str
    status: str


class EndSessionResponse(BaseModel):
    session_id: str
    status: str


class SetProviderRequest(BaseModel):
    provider: str = Field(min_length=1)


class SetModelRequest(BaseModel):
    model: str = Field(min_length=1)


class SetMcpRequest(BaseModel):
    enabled: bool
    profile_name: str | None = None


class SessionConfigResponse(BaseModel):
    session_id: str
    provider: str
    model: str
    mcp_enabled: bool
    mcp_profile_name: str | None
    subagent_name: str | None = None


class TurnAttachment(BaseModel):
    attachment_id: str
    filename: str
    content_type: str | None = None
    size: int = Field(ge=0)
    url: str


class SubmitTurnRequest(BaseModel):
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    text: str | None = None
    attachments: list[TurnAttachment] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1)


class SetSubagentRequest(BaseModel):
    name: str | None = None


class CodialRuleAddRequest(BaseModel):
    rule: str = Field(min_length=1)


class CodialRuleRemoveRequest(BaseModel):
    index: int = Field(ge=1)


class CodialRuleResponse(BaseModel):
    rules: list[str]
