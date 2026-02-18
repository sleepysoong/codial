from __future__ import annotations

from codial_service.app.providers.base import (
    ProviderAdapter,
    ProviderRequest,
    ProviderResponse,
)


class PlaceholderProviderAdapter(ProviderAdapter):
    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self._description = description

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            output_text=(
                f"`{self.name}` 프로바이더는 현재 플레이스홀더 단계예요. "
                f"{self._description} 요청은 `{request.text or '요청 없음'}`이에요."
            ),
            decision_summary=f"{self.name} 플레이스홀더 어댑터로 응답했어요.",
        )
