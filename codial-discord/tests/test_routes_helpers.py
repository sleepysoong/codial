from __future__ import annotations

from codial_discord.app.routes import (
    _extract_command_attachments,
    _extract_option_int,
    _format_codial_rule_list,
)


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


def test_extract_option_int_reads_integer_option() -> None:
    data = {"options": [{"name": "index", "value": 3}]}
    assert _extract_option_int(data, "index") == 3


def test_format_codial_rule_list_formats_ordered_lines() -> None:
    rendered = _format_codial_rule_list(["규칙 A", "규칙 B"])
    assert "1. 규칙 A" in rendered
    assert "2. 규칙 B" in rendered
