from __future__ import annotations

from codial_service.app.providers.base import ProviderAdapter
from libs.common.errors import ValidationError


class ProviderManager:
    def __init__(self, adapters: list[ProviderAdapter]) -> None:
        self._adapters = {adapter.name: adapter for adapter in adapters}

    def resolve(self, provider_name: str) -> ProviderAdapter:
        adapter = self._adapters.get(provider_name)
        if adapter is None:
            supported = ", ".join(sorted(self._adapters.keys()))
            raise ValidationError(
                f"지원하지 않는 프로바이더예요: `{provider_name}`. 지원 목록: {supported}"
            )
        return adapter
