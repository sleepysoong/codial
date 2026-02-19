"""URL에서 콘텐츠를 가져오는 도구예요."""

from __future__ import annotations

from typing import Any

import httpx

from codial_service.app.tools.base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    """HTTP(S) URL에서 텍스트 콘텐츠를 가져오는 도구예요."""

    def __init__(self, *, timeout_seconds: float = 15.0, max_bytes: int = 1_000_000) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "URL에서 텍스트 콘텐츠를 가져와요. "
            "웹 페이지, API 응답, 원격 파일 등을 읽을 수 있어요."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "가져올 URL이에요. http:// 또는 https:// 로 시작해야 해요.",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "HTTP 메서드예요. 기본값은 GET이에요.",
                },
                "headers": {
                    "type": "object",
                    "description": "추가 HTTP 헤더 딕셔너리예요.",
                    "additionalProperties": {"type": "string"},
                },
                "body": {
                    "type": "string",
                    "description": "POST 요청 시 전송할 본문이에요.",
                },
            },
            "required": ["url"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url")
        if not isinstance(url, str) or not url.strip():
            return ToolResult(ok=False, error="url 파라미터가 필요해요.")

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return ToolResult(ok=False, error="url은 http:// 또는 https:// 로 시작해야 해요.")

        method = arguments.get("method", "GET")
        if method not in ("GET", "POST"):
            return ToolResult(ok=False, error="method는 GET 또는 POST만 지원해요.")

        extra_headers = arguments.get("headers")
        if extra_headers is not None and not isinstance(extra_headers, dict):
            extra_headers = None

        body = arguments.get("body")

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                if method == "POST":
                    response = await client.post(
                        url,
                        content=body if isinstance(body, str) else None,
                        headers=extra_headers,
                    )
                else:
                    response = await client.get(url, headers=extra_headers)
        except httpx.TimeoutException:
            return ToolResult(ok=False, error="요청 시간이 초과됐어요.")
        except httpx.HTTPError as exc:
            return ToolResult(ok=False, error=f"HTTP 오류가 발생했어요: {exc}")

        content_bytes = response.content[: self._max_bytes]
        try:
            text = content_bytes.decode("utf-8", errors="replace")
        except Exception:
            text = content_bytes.decode("latin-1", errors="replace")

        truncated = len(response.content) > self._max_bytes
        return ToolResult(
            ok=True,
            output=text,
            metadata={
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "byte_count": len(response.content),
                "truncated": truncated,
            },
        )
