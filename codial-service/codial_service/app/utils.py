"""공통 유틸리티 함수예요."""

from __future__ import annotations

from typing import Any

import yaml


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """YAML 프론트매터와 본문을 분리해요.

    ``---`` 로 감싸인 YAML 블록이 있으면 파싱해서 반환하고,
    없으면 빈 딕셔너리와 원문을 반환해요.

    Args:
        text: 파싱할 원본 텍스트예요.

    Returns:
        ``(frontmatter_dict, body_text)`` 튜플이에요.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---\n"):
        return {}, text.strip()

    lines = stripped.splitlines()
    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, text.strip()

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    loaded = yaml.safe_load(frontmatter_text)
    if isinstance(loaded, dict):
        return loaded, body
    return {}, body


def normalize_str_list(value: object) -> list[str]:
    """문자열 또는 리스트 값을 정규화된 문자열 목록으로 변환해요.

    문자열이면 콤마로 분리하고, 리스트이면 문자열 항목만 추출해요.

    Args:
        value: 정규화할 값이에요.

    Returns:
        공백이 제거된 비어있지 않은 문자열 목록이에요.
    """
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
        return result
    return []
