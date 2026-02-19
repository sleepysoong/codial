"""Hashline 유틸리티예요.

각 코드 라인에 내용 기반 짧은 해시를 붙여서 LLM이 정확한 위치를
지정할 수 있게 해 줘요. 공백/들여쓰기 불일치로 인한 편집 실패를
방지하는 결정론적 앵커 역할을 해요.

형식: ``줄번호:해시| 코드내용``
예시: ``1:a3| def hello():``
"""

from __future__ import annotations

import hashlib


def generate_line_hash(content: str, *, length: int = 2) -> str:
    """라인 내용으로부터 짧은 해시를 생성해요.

    공백을 제거(strip)한 텍스트를 해싱하므로 들여쓰기 변경에
    강인해요.

    Args:
        content: 원본 라인 텍스트예요.
        length: 해시 길이(hex 문자 수)예요. 기본값 2 → 256가지.

    Returns:
        ``length`` 글자의 16진 해시 문자열이에요.
    """
    clean = content.strip()
    return hashlib.md5(clean.encode()).hexdigest()[:length]


def format_lines_with_hash(lines: list[str], *, start: int = 1) -> list[str]:
    """라인 목록에 ``줄번호:해시| 내용`` 형식을 적용해요.

    Args:
        lines: 원본 라인 문자열 리스트예요.
        start: 시작 줄 번호(1-indexed)예요.

    Returns:
        hashline 포맷이 적용된 문자열 리스트예요.
    """
    result: list[str] = []
    for i, line in enumerate(lines, start=start):
        h = generate_line_hash(line)
        result.append(f"{i}:{h}| {line}")
    return result


def build_hash_to_lineno_map(lines: list[str]) -> dict[str, list[int]]:
    """라인 목록으로부터 해시 → [줄 번호(0-indexed)] 매핑을 만들어요.

    같은 해시가 여러 줄에서 나올 수 있으므로 값은 리스트예요.

    Args:
        lines: 원본 라인 문자열 리스트예요.

    Returns:
        ``{hash_str: [idx, ...]}`` 딕셔너리예요.
    """
    mapping: dict[str, list[int]] = {}
    for idx, line in enumerate(lines):
        h = generate_line_hash(line)
        mapping.setdefault(h, []).append(idx)
    return mapping


def resolve_hash_to_index(
    hash_value: str,
    hash_map: dict[str, list[int]],
    *,
    hint_lineno: int | None = None,
) -> int | None:
    """해시 값을 0-indexed 라인 인덱스로 변환해요.

    동일 해시가 여러 줄에 존재하면 ``hint_lineno``(0-indexed)와
    가장 가까운 줄을 선택해요. hint가 없으면 첫 번째를 반환해요.

    Args:
        hash_value: 찾을 해시 문자열이에요.
        hash_map: ``build_hash_to_lineno_map`` 결과예요.
        hint_lineno: 모호성 해소용 힌트 줄 번호(0-indexed)예요.

    Returns:
        0-indexed 라인 인덱스, 또는 매칭 실패 시 ``None``이에요.
    """
    indices = hash_map.get(hash_value)
    if not indices:
        return None
    if len(indices) == 1:
        return indices[0]
    if hint_lineno is not None:
        return min(indices, key=lambda x: abs(x - hint_lineno))
    return indices[0]
