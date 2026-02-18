from __future__ import annotations

import pytest

from services.agent_core_api.app.attachment_ingestor import AttachmentIngestor
from services.agent_core_api.app.models import TurnAttachment


@pytest.mark.asyncio
async def test_attachment_ingestor_summarizes_without_download() -> None:
    ingestor = AttachmentIngestor(
        download_enabled=False,
        max_bytes=1_000_000,
        storage_dir=".runtime/tests",
        timeout_seconds=5.0,
    )
    attachments = [
        TurnAttachment(
            attachment_id="a1",
            filename="img.png",
            content_type="image/png",
            size=100,
            url="https://example.com/img.png",
        ),
        TurnAttachment(
            attachment_id="a2",
            filename="doc.txt",
            content_type="text/plain",
            size=100,
            url="https://example.com/doc.txt",
        ),
    ]

    result = await ingestor.ingest(session_id="s1", turn_id="t1", attachments=attachments)
    assert "첨부파일 2개" in result.summary
    assert result.downloaded_count == 0
