"""내장 도구의 추상 기반 클래스예요.

새 도구를 추가하려면 `BaseTool`을 상속하고 `name`, `description`,
`input_schema`, `execute`를 구현하면 돼요.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolResult:
    """도구 실행 결과를 담는 컨테이너예요."""

    ok: bool
    """실행 성공 여부예요."""

    output: str = ""
    """성공 시 텍스트 결과예요."""

    error: str = ""
    """실패 시 오류 메시지예요."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """추가 메타데이터 (바이트 수, 줄 수 등)예요."""


class BaseTool(abc.ABC):
    """모든 내장 도구가 구현해야 하는 추상 클래스예요.

    확장 방법:
        1. `BaseTool`을 상속하는 클래스를 만들어요.
        2. `name`, `description`, `input_schema` 프로퍼티를 구현해요.
        3. `execute` 메서드에 실제 로직을 작성해요.
        4. `ToolRegistry.register()`로 등록하면 끝이에요.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """도구의 고유 이름이에요. LLM이 호출할 때 사용돼요."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """도구가 무엇을 하는지 설명하는 문장이에요. LLM에게 전달돼요."""

    @property
    @abc.abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema 형식의 입력 파라미터 정의예요.

        예시::

            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "요청할 URL이에요."},
                },
                "required": ["url"],
            }
        """

    @abc.abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """도구를 실행하고 결과를 반환해요.

        Args:
            arguments: `input_schema`에 정의된 형태의 파라미터 딕셔너리예요.

        Returns:
            실행 결과를 담은 `ToolResult` 인스턴스예요.
        """

    def to_spec(self) -> dict[str, Any]:
        """프로바이더에 전달할 도구 스펙 딕셔너리를 생성해요."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
