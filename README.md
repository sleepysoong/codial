# 디스코드 코딩 에이전트 (Python)

이 저장소는 2개 서버 구조로 동작해요.

- `services/discord_gateway`: 디스코드 인터랙션 처리와 메시지 렌더링 경계 서버예요.
- `services/agent_core_api`: 세션 오케스트레이션, 워커, 프로바이더 연동 경계 서버예요.

## 개발 환경 실행 방법

먼저 의존성을 설치해요.

```bash
python -m pip install -e ".[dev]"
```

환경 변수 예시는 다음과 같아요.

```bash
set CORE_API_TOKEN=dev-core-token
set CORE_GATEWAY_BASE_URL=http://localhost:8080
set CORE_GATEWAY_INTERNAL_TOKEN=dev-internal-token
set CORE_OPENAI_API_KEY=your_openai_api_key
set CORE_WORKSPACE_ROOT=C:\\Users\\Administrator\\Desktop\\code
set CORE_CODEX_BRIDGE_BASE_URL=http://localhost:8091
set CORE_CODEX_BRIDGE_TOKEN=your_codex_bridge_token
set CORE_COPILOT_BRIDGE_BASE_URL=http://localhost:8092
set CORE_COPILOT_BRIDGE_TOKEN=your_copilot_bridge_token

set DGW_CORE_API_BASE_URL=http://localhost:8081
set DGW_CORE_API_TOKEN=dev-core-token
set DGW_INTERNAL_EVENT_TOKEN=dev-internal-token
set DGW_DISCORD_PUBLIC_KEY=your_discord_public_key
set DGW_DISCORD_BOT_TOKEN=your_discord_bot_token
```

코어 API 서버를 실행해요.

```bash
uvicorn services.agent_core_api.app.main:app --host 0.0.0.0 --port 8081 --reload
```

디스코드 게이트웨이 서버를 실행해요.

```bash
uvicorn services.discord_gateway.app.main:app --host 0.0.0.0 --port 8080 --reload
```

## 현재 구현 상태

- `start_chat` 버튼 인터랙션은 즉시 ACK하고 백그라운드에서 세션 채널을 준비해요.
- 코어 API는 세션을 생성하고, 게이트웨이는 디스코드 채널을 만든 뒤 세션에 바인딩해요.
- `/ask` 명령은 코어 워커 큐에 작업을 넣고, 구조화 이벤트를 디스코드에 출력해요.
- `/end` 명령은 세션 상태를 종료로 변경하고 채널에 안내 메시지를 남겨요.
- `/provider`, `/model`, `/mcp` 명령은 세션별 실행 설정을 변경해요.
- `/ask` 명령은 `attachment` 옵션으로 파일 1개를 함께 전달할 수 있어요.
- `openai-codex`와 `github-copilot-sdk`는 HTTP 브리지 방식으로 연결해요.

## 품질 검사 명령

아래 명령으로 린트, 타입 검사, 테스트를 실행해요.

```bash
python -m ruff check .
python -m mypy .
python -m pytest
```

## 주요 문서

- 상세 설계 초안: `draft.md`
- 에이전트 프로파일: `AGENTS.md`
- 프로젝트 규칙: `RULES.md`
- 스킬 정의: `skills/`
