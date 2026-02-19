from __future__ import annotations


class TurnEventType:
    """turn_worker에서 발행하는 이벤트 타입 상수예요."""

    PLAN = "plan"
    ACTION = "action"
    DECISION_SUMMARY = "decision_summary"
    RESPONSE_DELTA = "response_delta"
    FINAL = "final"
    ERROR = "error"
