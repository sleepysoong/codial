from __future__ import annotations

from services.discord_gateway.app.security import verify_discord_request


def test_verify_discord_request_returns_false_for_invalid_payload() -> None:
    result = verify_discord_request(
        public_key_hex="00" * 32,
        signature_hex="11" * 64,
        timestamp="1700000000",
        body=b"{}",
    )
    assert result is False
