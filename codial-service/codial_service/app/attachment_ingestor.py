from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from codial_service.app.models import TurnAttachment
from libs.common.errors import UpstreamTransientError


@dataclass(slots=True)
class AttachmentIngestResult:
    summary: str
    downloaded_count: int


class AttachmentIngestor:
    def __init__(
        self,
        *,
        download_enabled: bool,
        max_bytes: int,
        storage_dir: str,
        timeout_seconds: float,
    ) -> None:
        self._download_enabled = download_enabled
        self._max_bytes = max_bytes
        self._storage_dir = Path(storage_dir)
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=self._timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ingest(self, session_id: str, turn_id: str, attachments: list[TurnAttachment]) -> AttachmentIngestResult:
        if not attachments:
            return AttachmentIngestResult(summary="첨부파일이 없어요.", downloaded_count=0)

        image_count = 0
        file_count = 0
        downloaded_count = 0

        for attachment in attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                image_count += 1
            else:
                file_count += 1

            if self._download_enabled:
                await self._download_one(session_id=session_id, turn_id=turn_id, attachment=attachment)
                downloaded_count += 1

        summary = (
            f"첨부파일 {len(attachments)}개를 확인했어요. "
            f"이미지 {image_count}개, 일반 파일 {file_count}개예요."
        )
        if self._download_enabled:
            summary += f" 다운로드는 {downloaded_count}개 완료했어요."

        return AttachmentIngestResult(summary=summary, downloaded_count=downloaded_count)

    async def _download_one(self, session_id: str, turn_id: str, attachment: TurnAttachment) -> None:
        if attachment.size > self._max_bytes:
            return

        target_dir = self._storage_dir / session_id / turn_id
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = attachment.filename.replace("..", "_").replace("/", "_").replace("\\", "_")
        target_path = target_dir / safe_filename

        try:
            response = await self._client.get(attachment.url)
        except httpx.HTTPError as exc:
            raise UpstreamTransientError("첨부파일 다운로드 중 네트워크 오류가 발생했어요.") from exc

        if response.status_code >= 500:
            raise UpstreamTransientError("첨부파일 다운로드 서버 오류가 발생했어요.")
        response.raise_for_status()

        content = response.content
        if len(content) > self._max_bytes:
            return
        target_path.write_bytes(content)
