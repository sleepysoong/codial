from __future__ import annotations

from services.discord_gateway.app.routes import _extract_command_attachments


def test_extract_command_attachments_reads_resolved_payload() -> None:
    data = {
        "options": [{"name": "attachment", "value": "att-1"}],
        "resolved": {
            "attachments": {
                "att-1": {
                    "filename": "example.png",
                    "content_type": "image/png",
                    "size": 512,
                    "url": "https://cdn.test/example.png",
                }
            }
        },
    }

    attachments = _extract_command_attachments(data)
    assert len(attachments) == 1
    assert attachments[0]["attachment_id"] == "att-1"
    assert attachments[0]["filename"] == "example.png"
