# codial-service

`codial-service`는 Codial의 코어 API 서비스예요. 세션 상태, 정책 로딩, 턴 워커, 프로바이더 호출, MCP 연동을 담당해요.

이 문서는 다음 개발자가 바로 작업을 이어갈 수 있도록 **실행 방법 + 환경 변수 + API 명세 + 내부 동작 규약**을 자세히 정리해요.

## 1) 책임 범위

- Discord 요청 자체는 처리하지 않고, `codial-discord`가 호출하는 REST API만 제공해요.
- 세션 생성/종료/설정 변경을 관리해요.
- 사용자 턴을 큐에 넣고 비동기 워커로 처리해요.
- 현재 활성 프로바이더 정책을 검증하고 실제 Provider Bridge를 호출해요.
- MCP 서버와 JSON-RPC로 통신해 도구/프롬프트/리소스 메타를 조회해요.
- 처리 진행 이벤트를 `codial-discord`의 내부 엔드포인트로 푸시해요.

## 2) 현재 아키텍처 개요

- 앱 엔트리: `codial_service.app.main`
- 라우트: `codial_service.app.routes`
- 세션 저장소: `codial_service.app.store` (현재 인메모리)
- 워커: `codial_service.app.turn_worker`
- 프로바이더 매니저: `codial_service.app.providers.manager`
- 프로바이더 카탈로그: `codial_service.app.providers.catalog`
- Copilot 인증 부트스트랩: `codial_service.app.providers.copilot_auth`
- 정책 로딩: `codial_service.app.policy_loader`
- CODIAL 규칙 저장: `codial_service.app.codial_rules`
- MCP 클라이언트: `codial_service.app.mcp_client`

## 3) 실행 방법

## 의존성 설치

```bash
python -m pip install -e .
```

개발 도구 포함 설치:

```bash
python -m pip install -e ".[dev]"
```

## 실행

```bash
codial-service-dev
```

또는 프로덕션 모드:

```bash
codial-service
```

기본 포트는 `8081`이에요.

## 준비 확인

```bash
curl http://localhost:8081/v1/health/live
curl http://localhost:8081/v1/health/ready
```

## 4) 환경 변수 명세 (`CORE_*`)

`.env.example` 기준으로 관리해요.

| 변수 | 기본값 | 필수 여부 | 설명 |
| --- | --- | --- | --- |
| `CORE_HOST` | `0.0.0.0` | 선택 | 서비스 바인드 호스트예요. |
| `CORE_PORT` | `8081` | 선택 | 서비스 포트예요. |
| `CORE_API_TOKEN` | `dev-core-token` | 운영 필수 | `/v1/*` 보호용 Bearer 토큰이에요. |
| `CORE_GATEWAY_BASE_URL` | `http://localhost:8080` | 필수 | 이벤트 푸시 대상(`codial-discord`) 주소예요. |
| `CORE_GATEWAY_INTERNAL_TOKEN` | `dev-internal-token` | 운영 필수 | 내부 이벤트 전송 인증 토큰이에요. |
| `CORE_REQUEST_TIMEOUT_SECONDS` | `10` | 선택 | 일반 HTTP 요청 타임아웃이에요. |
| `CORE_TURN_WORKER_COUNT` | `2` | 선택 | 턴 처리 워커 개수예요. |
| `CORE_DEFAULT_PROVIDER_NAME` | `github-copilot-sdk` | 선택 | 활성 목록 비어 있을 때 fallback 기본값이에요. |
| `CORE_ENABLED_PROVIDER_NAMES` | `github-copilot-sdk` | 운영 필수 | 허용 프로바이더 CSV예요. 현재는 Copilot 단일을 권장해요. |
| `CORE_COPILOT_BRIDGE_BASE_URL` | - | Copilot 사용 시 필수 | Copilot Bridge 서버 주소예요. |
| `CORE_COPILOT_BRIDGE_TOKEN` | 빈 값 | 선택 | 브리지 토큰을 직접 주입할 때 사용해요. |
| `CORE_COPILOT_AUTO_LOGIN_ENABLED` | `true` | 선택 | 토큰 없을 때 자동 로그인 시도 여부예요. |
| `CORE_COPILOT_AUTH_CACHE_PATH` | `.runtime/copilot-auth.json` | 선택 | Copilot 토큰 캐시 파일 경로예요. |
| `CORE_COPILOT_LOGIN_ENDPOINT` | `/v1/auth/login` | 선택 | 브리지 로그인 엔드포인트 경로예요. |
| `CORE_PROVIDER_BRIDGE_TIMEOUT_SECONDS` | `30` | 선택 | Provider Bridge 호출 타임아웃이에요. |
| `CORE_MCP_SERVER_URL` | 빈 값 | 선택 | MCP 서버 주소예요. 비어 있으면 MCP 클라이언트를 만들지 않아요. |
| `CORE_MCP_SERVER_TOKEN` | 빈 값 | 선택 | MCP 인증 토큰이에요. |
| `CORE_MCP_REQUEST_TIMEOUT_SECONDS` | `15` | 선택 | MCP 호출 타임아웃이에요. |
| `CORE_ATTACHMENT_DOWNLOAD_ENABLED` | `false` | 선택 | 첨부파일 실제 다운로드 여부예요. |
| `CORE_ATTACHMENT_DOWNLOAD_MAX_BYTES` | `10000000` | 선택 | 첨부 다운로드 최대 크기예요. |
| `CORE_ATTACHMENT_STORAGE_DIR` | `.runtime/attachments` | 선택 | 첨부 저장 경로예요. |
| `CORE_WORKSPACE_ROOT` | `.` | 운영 필수 | `RULES.md`, `AGENTS.md`, `CODIAL.md`, `.claude/*` 탐색 기준 경로예요. |

## 5) 인증 규칙

- `/v1/*` 엔드포인트는 모두 `Authorization: Bearer <CORE_API_TOKEN>`이 필요해요.
- 토큰이 틀리면 `401`을 반환해요.
- 헬스체크(`/v1/health/*`)는 인증이 필요 없어요.

## 6) API 명세

Base path: `/v1`

## 6.1 세션 생성

- `POST /v1/sessions`
- Request:

```json
{
  "guild_id": "123",
  "requester_id": "456",
  "idempotency_key": "sha256-string"
}
```

- Response:

```json
{
  "session_id": "uuid",
  "status": "active"
}
```

동작 메모:

- `idempotency_key`가 같으면 기존 세션을 재사용해요.
- `AGENTS.md` 기본값과 활성 프로바이더 목록을 함께 반영해 기본 세션 설정을 만들어요.

## 6.2 세션 채널 바인딩

- `POST /v1/sessions/{session_id}/bind-channel`
- Request:

```json
{
  "channel_id": "789"
}
```

- Response:

```json
{
  "session_id": "uuid",
  "channel_id": "789",
  "status": "active"
}
```

## 6.3 세션 종료

- `POST /v1/sessions/{session_id}/end`

Response:

```json
{
  "session_id": "uuid",
  "status": "ended"
}
```

## 6.4 세션 프로바이더 변경

- `POST /v1/sessions/{session_id}/provider`
- Request:

```json
{
  "provider": "github-copilot-sdk"
}
```

- Response (`SessionConfigResponse`):

```json
{
  "session_id": "uuid",
  "provider": "github-copilot-sdk",
  "model": "gpt-5-mini",
  "mcp_enabled": true,
  "mcp_profile_name": "default",
  "subagent_name": null
}
```

동작 메모:

- `CORE_ENABLED_PROVIDER_NAMES`에 없는 값이면 `400`을 반환해요.

## 6.5 세션 모델 변경

- `POST /v1/sessions/{session_id}/model`
- Request:

```json
{
  "model": "gpt-5"
}
```

- Response: `SessionConfigResponse`

## 6.6 MCP 설정 변경

- `POST /v1/sessions/{session_id}/mcp`
- Request:

```json
{
  "enabled": true,
  "profile_name": "default"
}
```

- Response: `SessionConfigResponse`

## 6.7 서브에이전트 설정/해제

- `POST /v1/sessions/{session_id}/subagent`
- Request:

```json
{
  "name": "planner"
}
```

또는 해제:

```json
{
  "name": null
}
```

- Response: `SessionConfigResponse`

동작 메모:

- 유효한 서브에이전트는 아래 경로에서 탐색해요.
  - `~/.claude/agents/*.md`
  - `<CORE_WORKSPACE_ROOT>/.claude/agents/*.md`
- 없는 이름이면 `404`를 반환해요.

## 6.8 CODIAL 규칙 조회

- `GET /v1/codial/rules`

Response:

```json
{
  "rules": ["항상 한국어로 답변해요."]
}
```

## 6.9 CODIAL 규칙 추가

- `POST /v1/codial/rules`
- Request:

```json
{
  "rule": "응답은 항상 ~해요 체로 작성해요."
}
```

- Response:

```json
{
  "rules": ["..."]
}
```

## 6.10 CODIAL 규칙 제거

- `DELETE /v1/codial/rules`
- Request:

```json
{
  "index": 1
}
```

- Response:

```json
{
  "rules": ["..."]
}
```

동작 메모:

- `index`는 1부터 시작해요.
- 범위를 벗어나면 `400`을 반환해요.

## 6.11 턴 제출

- `POST /v1/sessions/{session_id}/turns`
- Request:

```json
{
  "session_id": "uuid",
  "user_id": "discord-user-id",
  "channel_id": "discord-channel-id",
  "text": "질문 내용",
  "attachments": [
    {
      "attachment_id": "att-1",
      "filename": "example.png",
      "content_type": "image/png",
      "size": 12345,
      "url": "https://cdn.discordapp.com/..."
    }
  ],
  "idempotency_key": "sha256-string"
}
```

- Response:

```json
{
  "status": "accepted",
  "trace_id": "uuid",
  "turn_id": "uuid"
}
```

동작 메모:

- 실제 모델 응답은 동기 응답으로 바로 주지 않고, 내부 이벤트 스트림으로 전달해요.
- 세션 종료 상태면 `409`를 반환해요.

## 6.12 헬스체크

- `GET /v1/health/live` -> `{ "status": "ok" }`
- `GET /v1/health/ready` -> `{ "status": "ok" }`

## 7) 워커 이벤트 프로토콜 (`codial-service` -> `codial-discord`)

서비스는 처리 중 이벤트를 `CORE_GATEWAY_BASE_URL/internal/stream-events`로 전송해요.

헤더:

- `x-internal-token: <CORE_GATEWAY_INTERNAL_TOKEN>`

Payload 형식:

```json
{
  "session_id": "uuid",
  "turn_id": "uuid",
  "type": "plan",
  "payload": {
    "text": "진행 메시지"
  }
}
```

현재 사용 이벤트 타입:

- `plan`
- `action`
- `decision_summary`
- `response_delta`
- `final`
- `error`

## 8) 정책/메모리/스킬 로딩 규칙

`PolicyLoader`는 아래를 통합 로딩해요.

- `RULES.md`
- `CODIAL.md`
- `AGENTS.md`
- `.claude/skills`, `.claude/commands`, `skills/*.yaml`
- `CLAUDE.md` 체인 (`~/.claude/CLAUDE.md` + workspace 상향)

주의:

- `RULES.md`와 `CODIAL.md` 내용은 합쳐서 정책 텍스트로 사용해요.
- `AGENTS.md`의 `default_provider`, `default_model`, `default_mcp_*`를 세션 생성 기본값에 반영해요.

## 9) 프로바이더 구조와 확장 포인트

현재 활성 운영 정책:

- `github-copilot-sdk`만 활성화

구조상 지원 대상:

- `github-copilot-sdk`

확장 방법:

1. `codial_service.app.providers.base.ProviderAdapter` 구현체를 추가해요.
2. `codial_service.app.providers.catalog`에 이름/설정 매핑을 추가해요.
3. `CORE_ENABLED_PROVIDER_NAMES`에 신규 이름을 넣어 활성화해요.
4. 필요하면 `RULES.md` allow/deny 정책도 같이 조정해요.

## 10) Copilot 자동 로그인 규약

초기화 순서:

1. `CORE_COPILOT_BRIDGE_TOKEN`이 있으면 즉시 사용하고 캐시를 갱신해요.
2. 없으면 `CORE_COPILOT_AUTH_CACHE_PATH` 캐시를 읽어요.
3. 캐시도 없고 `CORE_COPILOT_AUTO_LOGIN_ENABLED=true`면 `CORE_COPILOT_LOGIN_ENDPOINT`로 로그인 호출해요.

로그인 응답에서 인식하는 토큰 키:

- `token`
- `access_token`
- `bearer_token`
- `api_key`
- `data` 내부 중첩 동일 키

## 11) MCP 연동 요약

- 초기화: `initialize` + `notifications/initialized`
- 조회: `tools/list`, `prompts/list`, `resources/list`, `resources/templates/list`
- 호출: `tools/call`
- 헬스: `ping`
- 페이지네이션: `nextCursor`를 따라 자동 순회해요.

턴 처리 시 MCP 동작:

1. 워커가 MCP 도구 메타를 조회해 프로바이더 브리지로 전달해요.
2. 브리지가 `tool_requests`를 반환하면 코어가 `tools/call`로 실제 MCP 도구를 실행해요.
3. 실행 결과(`tool_results`)를 다시 브리지에 재주입해 최종 답변을 완성해요.
4. 최대 도구 호출 라운드는 5회로 제한해요.

현재 transport는 HTTP JSON-RPC 기반이에요.

## 12) 운영상 주의점

- 세션 저장소가 인메모리라 재시작 시 세션이 유지되지 않아요.
- 워커 큐도 프로세스 메모리 기반이라 재시작 시 대기 작업이 유실돼요.
- 운영 환경에서는 리버스 프록시/TLS/비밀값 관리(Secret Manager)를 반드시 붙여요.

## 13) 개발 체크리스트

```bash
python -m ruff check .
python -m mypy .
python -m pytest
```
