from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Coroutine
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from libs.common.logging import get_logger
from services.discord_gateway.app.core_api_client import CoreApiClient
from services.discord_gateway.app.discord_api_client import DiscordApiClient
from services.discord_gateway.app.security import verify_discord_request
from services.discord_gateway.app.session_store import store
from services.discord_gateway.app.settings import settings

router = APIRouter()
logger = get_logger("discord_gateway.routes")
_job_semaphore = asyncio.Semaphore(settings.max_concurrent_background_jobs)


def _schedule_background_job(coro: Coroutine[Any, Any, None], *, job_name: str) -> None:
    task = asyncio.create_task(coro)

    def _on_done(completed_task: asyncio.Task[None]) -> None:
        if completed_task.cancelled():
            logger.warning("background_job_cancelled", job_name=job_name)
            return
        error = completed_task.exception()
        if error is not None:
            logger.exception("background_job_failed", job_name=job_name, error=str(error))

    task.add_done_callback(_on_done)


def _interaction_idempotency_key(interaction: dict[str, Any]) -> str:
    raw = f"{interaction.get('id', '')}:{interaction.get('token', '')}".encode()
    return hashlib.sha256(raw).hexdigest()


def _turn_idempotency_key(interaction: dict[str, Any]) -> str:
    raw = f"turn:{interaction.get('id', '')}:{interaction.get('token', '')}".encode()
    return hashlib.sha256(raw).hexdigest()


def _extract_user_id(payload: dict[str, Any]) -> str:
    member = payload.get("member")
    if isinstance(member, dict):
        user = member.get("user")
        if isinstance(user, dict):
            value = user.get("id")
            if isinstance(value, str):
                return value
    user = payload.get("user")
    if isinstance(user, dict):
        value = user.get("id")
        if isinstance(value, str):
            return value
    return ""


def _extract_command_text(data: dict[str, Any]) -> str:
    options = data.get("options", [])
    if not isinstance(options, list):
        return ""
    for option in options:
        if isinstance(option, dict) and option.get("name") == "text":
            value = option.get("value")
            if isinstance(value, str):
                return value
    return ""


def _extract_option_value(data: dict[str, Any], option_name: str) -> Any:
    options = data.get("options", [])
    if not isinstance(options, list):
        return None
    for option in options:
        if isinstance(option, dict) and option.get("name") == option_name:
            return option.get("value")
    return None


def _extract_option_string(data: dict[str, Any], option_name: str) -> str:
    value = _extract_option_value(data, option_name)
    if isinstance(value, str):
        return value
    return ""


def _extract_option_bool(data: dict[str, Any], option_name: str, default: bool) -> bool:
    value = _extract_option_value(data, option_name)
    if isinstance(value, bool):
        return value
    return default


def _extract_command_attachments(data: dict[str, Any]) -> list[dict[str, Any]]:
    options = data.get("options", [])
    if not isinstance(options, list):
        return []

    resolved = data.get("resolved", {})
    resolved_attachments = resolved.get("attachments", {}) if isinstance(resolved, dict) else {}
    if not isinstance(resolved_attachments, dict):
        return []

    collected: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        if option.get("name") != "attachment":
            continue

        attachment_id = option.get("value")
        if not isinstance(attachment_id, str):
            continue

        attachment_payload = resolved_attachments.get(attachment_id)
        if not isinstance(attachment_payload, dict):
            continue

        filename = attachment_payload.get("filename")
        url = attachment_payload.get("url")
        size = attachment_payload.get("size")
        if not isinstance(filename, str) or not isinstance(url, str):
            continue
        if not isinstance(size, int):
            continue

        content_type_value = attachment_payload.get("content_type")
        content_type = content_type_value if isinstance(content_type_value, str) else None

        collected.append(
            {
                "attachment_id": attachment_id,
                "filename": filename,
                "content_type": content_type,
                "size": size,
                "url": url,
            }
        )
    return collected


def _channel_name(session_id: str) -> str:
    suffix = session_id.replace("-", "")[:8]
    return f"{settings.session_channel_prefix}-{suffix}"


async def _provision_session_channel(payload: dict[str, Any]) -> None:
    async with _job_semaphore:
        guild_id = payload.get("guild_id", "")
        requester_id = _extract_user_id(payload)
        app_id = payload.get("application_id", "")
        interaction_token = payload.get("token", "")

        if not isinstance(guild_id, str) or not guild_id:
            logger.error("missing_guild_id")
            return
        if not requester_id:
            logger.error("missing_requester_id", guild_id=guild_id)
            return

        core_client = CoreApiClient(
            base_url=settings.core_api_base_url,
            token=settings.core_api_token,
            timeout_seconds=settings.request_timeout_seconds,
        )
        discord_client = DiscordApiClient(
            bot_token=settings.discord_bot_token,
            timeout_seconds=settings.request_timeout_seconds,
        )

        idempotency_key = _interaction_idempotency_key(payload)
        trace_id = str(uuid.uuid4())

        try:
            session = await core_client.create_session(guild_id, requester_id, idempotency_key)
            session_id_value = session.get("session_id")
            if not isinstance(session_id_value, str):
                raise ValueError("session_id missing from core response")

            permission_overwrites = [
                {
                    "id": guild_id,
                    "type": 0,
                    "deny": str(1024),
                    "allow": "0",
                },
                {
                    "id": requester_id,
                    "type": 1,
                    "allow": str(1024),
                    "deny": "0",
                },
            ]

            channel = await discord_client.create_guild_text_channel(
                guild_id=guild_id,
                name=_channel_name(session_id_value),
                parent_id=settings.session_category_id,
                permission_overwrites=permission_overwrites,
            )
            channel_id_value = channel.get("id")
            if not isinstance(channel_id_value, str):
                raise ValueError("channel_id missing from discord response")

            await core_client.bind_channel(session_id_value, channel_id_value)
            await store.put(session_id=session_id_value, channel_id=channel_id_value)

            await discord_client.create_channel_message(
                channel_id=channel_id_value,
                content=(
                    f"세션 채널을 준비했어요.\\n"
                    f"- 세션 ID: `{session_id_value}`\\n"
                    f"- 채널: <#{channel_id_value}>\\n"
                    "`/ask text:<요청>` 명령으로 시작해요.\\n"
                    "설정 변경은 `/provider`, `/model`, `/mcp`, `/end` 명령을 사용해요."
                ),
            )
            if isinstance(app_id, str) and app_id and isinstance(interaction_token, str) and interaction_token:
                await discord_client.create_followup_message(
                    application_id=app_id,
                    interaction_token=interaction_token,
                    content=f"세션 채널을 만들었어요: <#{channel_id_value}>",
                    ephemeral=True,
                )

            logger.info(
                "session_channel_provisioned",
                trace_id=trace_id,
                session_id=session_id_value,
                channel_id=channel_id_value,
                guild_id=guild_id,
            )
        except Exception as exc:
            logger.exception("session_channel_provision_failed", trace_id=trace_id, error=str(exc))
            if isinstance(app_id, str) and app_id and isinstance(interaction_token, str) and interaction_token:
                try:
                    await discord_client.create_followup_message(
                        application_id=app_id,
                        interaction_token=interaction_token,
                        content="세션 준비에 실패했어요. 잠시 뒤에 다시 시도해요.",
                        ephemeral=True,
                    )
                except Exception as followup_exc:
                    logger.exception(
                        "session_failure_followup_failed",
                        trace_id=trace_id,
                        error=str(followup_exc),
                    )


async def _submit_turn_from_command(payload: dict[str, Any]) -> None:
    async with _job_semaphore:
        channel_id = payload.get("channel_id", "")
        user_id = _extract_user_id(payload)
        data = payload.get("data", {})
        text = _extract_command_text(data) if isinstance(data, dict) else ""
        attachments = _extract_command_attachments(data) if isinstance(data, dict) else []

        if not isinstance(channel_id, str) or not channel_id:
            logger.error("missing_channel_id_for_turn")
            return
        if not user_id:
            logger.error("missing_user_id_for_turn", channel_id=channel_id)
            return

        binding = await store.get_by_channel_id(channel_id)
        if binding is None:
            logger.warning("turn_dropped_channel_not_bound", channel_id=channel_id)
            return

        core_client = CoreApiClient(
            base_url=settings.core_api_base_url,
            token=settings.core_api_token,
            timeout_seconds=settings.request_timeout_seconds,
        )

        idempotency_key = _turn_idempotency_key(payload)
        try:
            await core_client.submit_turn(
                session_id=binding.session_id,
                user_id=user_id,
                channel_id=channel_id,
                text=text,
                attachments=attachments,
                idempotency_key=idempotency_key,
            )
            logger.info("turn_submitted", session_id=binding.session_id, channel_id=channel_id)
        except Exception as exc:
            logger.exception("turn_submit_failed", session_id=binding.session_id, error=str(exc))


async def _set_provider_from_command(payload: dict[str, Any]) -> None:
    async with _job_semaphore:
        channel_id = payload.get("channel_id", "")
        data = payload.get("data", {})
        provider = _extract_option_string(data, "provider") if isinstance(data, dict) else ""
        if not isinstance(channel_id, str) or not channel_id:
            logger.error("missing_channel_id_for_provider")
            return
        if not provider:
            logger.error("missing_provider_option", channel_id=channel_id)
            return

        binding = await store.get_by_channel_id(channel_id)
        if binding is None:
            logger.warning("provider_update_dropped_channel_not_bound", channel_id=channel_id)
            return

        core_client = CoreApiClient(
            base_url=settings.core_api_base_url,
            token=settings.core_api_token,
            timeout_seconds=settings.request_timeout_seconds,
        )
        discord_client = DiscordApiClient(
            bot_token=settings.discord_bot_token,
            timeout_seconds=settings.request_timeout_seconds,
        )

        try:
            config = await core_client.set_provider(binding.session_id, provider)
            current_model = config.get("model", "")
            await discord_client.create_channel_message(
                channel_id=channel_id,
                content=f"프로바이더를 `{provider}`로 변경했어요. 현재 모델은 `{current_model}`이에요.",
            )
            logger.info("provider_updated", session_id=binding.session_id, provider=provider)
        except Exception as exc:
            logger.exception("provider_update_failed", session_id=binding.session_id, error=str(exc))


async def _set_model_from_command(payload: dict[str, Any]) -> None:
    async with _job_semaphore:
        channel_id = payload.get("channel_id", "")
        data = payload.get("data", {})
        model_name = _extract_option_string(data, "model") if isinstance(data, dict) else ""
        if not isinstance(channel_id, str) or not channel_id:
            logger.error("missing_channel_id_for_model")
            return
        if not model_name:
            logger.error("missing_model_option", channel_id=channel_id)
            return

        binding = await store.get_by_channel_id(channel_id)
        if binding is None:
            logger.warning("model_update_dropped_channel_not_bound", channel_id=channel_id)
            return

        core_client = CoreApiClient(
            base_url=settings.core_api_base_url,
            token=settings.core_api_token,
            timeout_seconds=settings.request_timeout_seconds,
        )
        discord_client = DiscordApiClient(
            bot_token=settings.discord_bot_token,
            timeout_seconds=settings.request_timeout_seconds,
        )

        try:
            config = await core_client.set_model(binding.session_id, model_name)
            current_provider = config.get("provider", "")
            await discord_client.create_channel_message(
                channel_id=channel_id,
                content=f"모델을 `{model_name}`으로 변경했어요. 현재 프로바이더는 `{current_provider}`예요.",
            )
            logger.info("model_updated", session_id=binding.session_id, model=model_name)
        except Exception as exc:
            logger.exception("model_update_failed", session_id=binding.session_id, error=str(exc))


async def _set_mcp_from_command(payload: dict[str, Any]) -> None:
    async with _job_semaphore:
        channel_id = payload.get("channel_id", "")
        data = payload.get("data", {})
        enabled = _extract_option_bool(data, "enabled", default=True) if isinstance(data, dict) else True
        profile_name_value = _extract_option_value(data, "profile") if isinstance(data, dict) else None
        profile_name = profile_name_value if isinstance(profile_name_value, str) else None

        if not isinstance(channel_id, str) or not channel_id:
            logger.error("missing_channel_id_for_mcp")
            return

        binding = await store.get_by_channel_id(channel_id)
        if binding is None:
            logger.warning("mcp_update_dropped_channel_not_bound", channel_id=channel_id)
            return

        core_client = CoreApiClient(
            base_url=settings.core_api_base_url,
            token=settings.core_api_token,
            timeout_seconds=settings.request_timeout_seconds,
        )
        discord_client = DiscordApiClient(
            bot_token=settings.discord_bot_token,
            timeout_seconds=settings.request_timeout_seconds,
        )

        try:
            config = await core_client.set_mcp(
                session_id=binding.session_id,
                enabled=enabled,
                profile_name=profile_name,
            )
            mcp_state = "활성" if bool(config.get("mcp_enabled")) else "비활성"
            profile_text = config.get("mcp_profile_name") or "없음"
            await discord_client.create_channel_message(
                channel_id=channel_id,
                content=f"MCP를 `{mcp_state}` 상태로 변경했어요. 프로필은 `{profile_text}`예요.",
            )
            logger.info(
                "mcp_updated",
                session_id=binding.session_id,
                enabled=enabled,
                profile_name=profile_name,
            )
        except Exception as exc:
            logger.exception("mcp_update_failed", session_id=binding.session_id, error=str(exc))


async def _end_session_from_command(payload: dict[str, Any]) -> None:
    async with _job_semaphore:
        channel_id = payload.get("channel_id", "")
        if not isinstance(channel_id, str) or not channel_id:
            logger.error("missing_channel_id_for_end")
            return

        binding = await store.get_by_channel_id(channel_id)
        if binding is None:
            logger.warning("session_end_dropped_channel_not_bound", channel_id=channel_id)
            return

        core_client = CoreApiClient(
            base_url=settings.core_api_base_url,
            token=settings.core_api_token,
            timeout_seconds=settings.request_timeout_seconds,
        )
        discord_client = DiscordApiClient(
            bot_token=settings.discord_bot_token,
            timeout_seconds=settings.request_timeout_seconds,
        )

        try:
            await core_client.end_session(binding.session_id)
            await discord_client.create_channel_message(
                channel_id=channel_id,
                content="세션을 종료했어요. 새 세션이 필요하면 메인 채널에서 다시 시작해요.",
            )
            logger.info("session_ended", session_id=binding.session_id, channel_id=channel_id)
        except Exception as exc:
            logger.exception("session_end_failed", session_id=binding.session_id, error=str(exc))


@router.post("/discord/interactions")
async def discord_interactions(
    request: Request,
    x_signature_ed25519: str = Header(default=""),
    x_signature_timestamp: str = Header(default=""),
) -> dict[str, Any]:
    raw_body = await request.body()

    if not verify_discord_request(
        settings.discord_public_key,
        x_signature_ed25519,
        x_signature_timestamp,
        raw_body,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="서명 검증에 실패했어요.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="요청 본문 JSON이 올바르지 않아요.") from exc

    interaction_type = payload.get("type")
    if interaction_type == 1:
        return {"type": 1}

    data = payload.get("data", {})
    custom_id = data.get("custom_id", "")

    if interaction_type == 3 and custom_id == "start_chat":
        _schedule_background_job(_provision_session_channel(payload), job_name="provision_session_channel")
        return {
            "type": 5,
            "data": {"flags": 64},
        }

    if interaction_type == 2:
        command_name = data.get("name", "")
        if command_name == "ask":
            _schedule_background_job(_submit_turn_from_command(payload), job_name="submit_turn_from_command")
            return {"type": 5, "data": {"flags": 64}}
        if command_name == "end":
            _schedule_background_job(_end_session_from_command(payload), job_name="end_session_from_command")
            return {"type": 5, "data": {"flags": 64}}
        if command_name == "provider":
            _schedule_background_job(_set_provider_from_command(payload), job_name="set_provider_from_command")
            return {"type": 5, "data": {"flags": 64}}
        if command_name == "model":
            _schedule_background_job(_set_model_from_command(payload), job_name="set_model_from_command")
            return {"type": 5, "data": {"flags": 64}}
        if command_name == "mcp":
            _schedule_background_job(_set_mcp_from_command(payload), job_name="set_mcp_from_command")
            return {"type": 5, "data": {"flags": 64}}

    # Fallback deferred ack for unknown interactions.
    return {"type": 5}


@router.post("/internal/stream-events")
async def internal_stream_events(request: Request, x_internal_token: str = Header(default="")) -> dict[str, str]:
    if x_internal_token != settings.internal_event_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="내부 토큰 인증에 실패했어요.")

    event = await request.json()
    logger.info("stream_event", event_type=event.get("type"), session_id=event.get("session_id"))

    session_id = event.get("session_id")
    event_type = event.get("type")
    payload = event.get("payload", {})

    if isinstance(session_id, str) and isinstance(event_type, str):
        binding = await store.get_by_session_id(session_id)
        if binding is not None and isinstance(payload, dict):
            text = payload.get("text", "")
            if isinstance(text, str) and text:
                discord_client = DiscordApiClient(
                    bot_token=settings.discord_bot_token,
                    timeout_seconds=settings.request_timeout_seconds,
                )
                try:
                    await discord_client.create_channel_message(
                        channel_id=binding.channel_id,
                        content=f"[{event_type}] {text}",
                    )
                except Exception as exc:
                    logger.exception(
                        "stream_render_failed",
                        session_id=session_id,
                        channel_id=binding.channel_id,
                        error=str(exc),
                    )
    return {"status": "accepted"}


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> dict[str, str]:
    if not settings.core_api_base_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="코어 API 주소가 없어요.")
    if not settings.core_api_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="코어 API 토큰이 없어요.")
    return {"status": "ok"}
