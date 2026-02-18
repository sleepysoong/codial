---
name: session-bootstrap
description: 디스코드 세션 채널을 생성하고 초기 상태를 점검할 때 사용해요.
disable-model-invocation: false
user-invocable: true
allowed-tools: Read, Grep
---

# Session Bootstrap

세션을 시작할 때 다음 순서로 점검해요.

1. 세션 ID와 채널 바인딩 상태를 확인해요.
2. 현재 provider/model/mcp 설정을 확인해요.
3. 사용 가능한 기술 목록을 확인해요.
4. 사용자에게 다음 실행 명령(`/ask`, `/provider`, `/model`, `/mcp`, `/end`)을 안내해요.
