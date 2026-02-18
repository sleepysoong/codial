from __future__ import annotations

from openai import AsyncOpenAI

from libs.common.errors import ConfigurationError, UpstreamTransientError
from services.agent_core_api.app.providers.base import (
    ProviderAdapter,
    ProviderRequest,
    ProviderResponse,
)


class OpenAiProviderAdapter(ProviderAdapter):
    name = "openai-api"

    def __init__(self, api_key: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self._api_key:
            raise ConfigurationError("OpenAI API 키가 설정되지 않았어요.")

        client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout_seconds)

        attachment_summary = "없음"
        if request.attachments:
            names = [attachment.filename for attachment in request.attachments]
            attachment_summary = ", ".join(names)

        prompt = (
            "다음 정보를 반영해서 한국어 존댓말로 간결하고 정확하게 답변해요.\n"
            f"- 사용자 요청: {request.text or '요청 본문 없음'}\n"
            f"- 첨부파일: {attachment_summary}\n"
            f"- MCP 활성화: {request.mcp_enabled}\n"
            f"- MCP 프로필: {request.mcp_profile_name or '없음'}\n"
            f"- CLAUDE.md 메모리: {request.claude_memory_summary}\n"
            f"- RULES 요약: {request.rules_summary}\n"
            f"- AGENTS 요약: {request.agents_summary}\n"
            f"- Skills 요약: {request.skills_summary}\n"
        )

        try:
            response = await client.responses.create(
                model=request.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
            )
        except Exception as exc:
            raise UpstreamTransientError("OpenAI 응답 생성에 실패했어요.") from exc

        output_text = response.output_text.strip() if response.output_text else "응답이 비어 있어요."
        return ProviderResponse(
            output_text=output_text,
            decision_summary="OpenAI API로 응답을 생성했어요.",
        )
