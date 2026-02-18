from __future__ import annotations

from typing import Any


def build_application_commands() -> list[dict[str, Any]]:
    return [
        {
            "name": "ask",
            "description": "세션에 요청을 보내요.",
            "type": 1,
            "options": [
                {
                    "type": 3,
                    "name": "text",
                    "description": "요청 텍스트를 입력해요.",
                    "required": False,
                },
                {
                    "type": 11,
                    "name": "attachment",
                    "description": "첨부파일 1개를 전달해요.",
                    "required": False,
                },
            ],
        },
        {
            "name": "end",
            "description": "현재 세션을 종료해요.",
            "type": 1,
        },
        {
            "name": "provider",
            "description": "세션 프로바이더를 변경해요.",
            "type": 1,
            "options": [
                {
                    "type": 3,
                    "name": "provider",
                    "description": "프로바이더를 선택해요.",
                    "required": True,
                    "choices": [
                        {
                            "name": "github-copilot-sdk",
                            "value": "github-copilot-sdk",
                        }
                    ],
                }
            ],
        },
        {
            "name": "model",
            "description": "세션 모델을 변경해요.",
            "type": 1,
            "options": [
                {
                    "type": 3,
                    "name": "model",
                    "description": "모델 이름을 입력해요.",
                    "required": True,
                }
            ],
        },
        {
            "name": "mcp",
            "description": "MCP 설정을 변경해요.",
            "type": 1,
            "options": [
                {
                    "type": 5,
                    "name": "enabled",
                    "description": "MCP 활성화 여부예요.",
                    "required": False,
                },
                {
                    "type": 3,
                    "name": "profile",
                    "description": "MCP 프로필 이름이에요.",
                    "required": False,
                },
            ],
        },
        {
            "name": "subagent",
            "description": "서브에이전트를 설정하거나 해제해요.",
            "type": 1,
            "options": [
                {
                    "type": 3,
                    "name": "name",
                    "description": "서브에이전트 이름(해제: none/해제)",
                    "required": False,
                }
            ],
        },
        {
            "name": "rules_list",
            "description": "CODIAL 규칙 목록을 보여줘요.",
            "type": 1,
        },
        {
            "name": "rules_add",
            "description": "CODIAL 규칙을 추가해요.",
            "type": 1,
            "options": [
                {
                    "type": 3,
                    "name": "rule",
                    "description": "추가할 규칙 텍스트예요.",
                    "required": True,
                }
            ],
        },
        {
            "name": "rules_remove",
            "description": "CODIAL 규칙을 제거해요.",
            "type": 1,
            "options": [
                {
                    "type": 4,
                    "name": "index",
                    "description": "제거할 규칙 번호예요.",
                    "required": True,
                    "min_value": 1,
                }
            ],
        },
        {
            "name": "규칙목록",
            "description": "CODIAL 규칙 목록을 보여줘요.",
            "type": 1,
        },
        {
            "name": "규칙추가",
            "description": "CODIAL 규칙을 추가해요.",
            "type": 1,
            "options": [
                {
                    "type": 3,
                    "name": "rule",
                    "description": "추가할 규칙 텍스트예요.",
                    "required": True,
                }
            ],
        },
        {
            "name": "규칙제거",
            "description": "CODIAL 규칙을 제거해요.",
            "type": 1,
            "options": [
                {
                    "type": 4,
                    "name": "index",
                    "description": "제거할 규칙 번호예요.",
                    "required": True,
                    "min_value": 1,
                }
            ],
        },
    ]
