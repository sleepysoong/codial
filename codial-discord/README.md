# codial-discord

`codial-discord`는 Discord Interactions를 처리하는 게이트웨이 서비스예요. 이 서비스는 모델을 직접 호출하지 않고, `codial-service` REST API를 호출해 세션/턴 작업을 위임해요.

이 문서는 Discord 앱 세팅부터 커맨드 명세, 내부 이벤트 프로토콜까지 상세하게 정리해요.

## 1) 책임 범위

- Discord 요청 서명 검증(Ed25519)
- `start_chat` 버튼 및 슬래시 명령 처리
- 세션 채널 생성/안내 메시지 전송
- 코어 API(`codial-service`) 호출
- 코어 워커 이벤트를 채널 메시지로 렌더링

## 2) 실행 방법

## 설치

```bash
python -m pip install -e .
```

개발 도구 포함:

```bash
python -m pip install -e ".[dev]"
```

## 실행

```bash
codial-discord-dev
```

또는 프로덕션 모드:

```bash
codial-discord
```

기본 포트는 `8080`이에요.

## 3) Discord 앱 세팅 가이드 (상세)

## 3.1 애플리케이션/봇 생성

1. Discord Developer Portal에서 New Application을 만들어요.
2. `Bot` 탭에서 봇을 생성해요.
3. 아래 값을 확보해요.
   - Application ID -> `DGW_DISCORD_APPLICATION_ID`
   - Bot Token -> `DGW_DISCORD_BOT_TOKEN`
   - Public Key -> `DGW_DISCORD_PUBLIC_KEY`

## 3.2 OAuth2 설치 링크 생성

권장 scope:

- `bot`
- `applications.commands`

권장 봇 권한(최소):

- `View Channels`
- `Send Messages`
- `Embed Links` (선택)
- `Manage Channels` (세션 채널 생성용)

운영 방식에 따라 `Read Message History`도 추가해요.

## 3.3 Interaction Endpoint 설정

Portal의 Interactions Endpoint URL에 아래 경로를 등록해요.

- `https://<your-domain>/discord/interactions`

주의:

- HTTPS 종단이 필요해요.
- 프록시 사용 시 원본 바디가 변형되지 않게 설정해요.

## 3.4 슬래시 커맨드 동기화

`.env`를 채운 뒤 아래 명령으로 커맨드를 일괄 동기화해요.

```bash
codial-discord-sync-commands
```

- `DGW_DISCORD_COMMAND_GUILD_ID`를 지정하면 길드 스코프로 빠르게 반영돼요.
- 비워두면 글로벌 커맨드로 등록돼요(전파 시간이 더 걸릴 수 있어요).

## 4) 환경 변수 명세 (`DGW_*`)

`.env.example` 기준이에요.

| 변수 | 기본값 | 필수 여부 | 설명 |
| --- | --- | --- | --- |
| `DGW_HOST` | `0.0.0.0` | 선택 | 서비스 바인드 호스트예요. |
| `DGW_PORT` | `8080` | 선택 | 서비스 포트예요. |
| `DGW_CORE_API_BASE_URL` | `http://localhost:8081` | 필수 | 코어 API 주소예요. |
| `DGW_CORE_API_TOKEN` | `dev-core-token` | 필수 | 코어 API Bearer 토큰이에요. |
| `DGW_INTERNAL_EVENT_TOKEN` | `dev-internal-token` | 필수 | 내부 스트림 이벤트 인증 토큰이에요. |
| `DGW_REQUEST_TIMEOUT_SECONDS` | `10` | 선택 | 외부 HTTP 호출 타임아웃이에요. |
| `DGW_MAX_CONCURRENT_BACKGROUND_JOBS` | `20` | 선택 | 백그라운드 작업 동시성 제한이에요. |
| `DGW_DISCORD_PUBLIC_KEY` | 빈 값 | 필수 | Discord 요청 서명 검증 키예요. |
| `DGW_DISCORD_BOT_TOKEN` | 빈 값 | 필수 | Discord REST API 호출 토큰이에요. |
| `DGW_DISCORD_APPLICATION_ID` | 빈 값 | 커맨드 동기화 시 필수 | 커맨드 등록 대상 앱 ID예요. |
| `DGW_DISCORD_COMMAND_GUILD_ID` | 빈 값 | 선택 | 커맨드 길드 스코프(테스트용)예요. |
| `DGW_SESSION_CHANNEL_PREFIX` | `ai` | 선택 | 세션 채널 이름 prefix예요. |
| `DGW_SESSION_CATEGORY_ID` | 빈 값 | 선택 | 세션 채널 생성 대상 카테고리 ID예요. |
| `DGW_SESSION_CHANNEL_TOPIC_TEMPLATE` | `AI coding session: {session_id}` | 선택 | 현재 코드에서 토픽 적용은 사용하지 않아요. |

## 5) 공개 엔드포인트 명세

## 5.1 Discord Interactions

- `POST /discord/interactions`

필수 헤더:

- `X-Signature-Ed25519`
- `X-Signature-Timestamp`

핵심 동작:

- type `1` (Ping) -> `{ "type": 1 }`
- type `3` + `custom_id=start_chat` -> deferred ack 후 세션 채널 프로비저닝
- type `2` (Application Command) -> 명령별 비동기 작업 예약 후 deferred ack

## 5.2 내부 스트림 이벤트 수신

- `POST /internal/stream-events`

필수 헤더:

- `x-internal-token: <DGW_INTERNAL_EVENT_TOKEN>`

Payload 예시:

```json
{
  "session_id": "uuid",
  "turn_id": "uuid",
  "type": "plan",
  "payload": {
    "text": "요청을 분석 중이에요."
  }
}
```

렌더링 규칙:

- `payload.text`가 있으면 세션 채널에 `[type] text` 형식으로 메시지를 전송해요.

## 5.3 헬스체크

- `GET /health/live` -> liveness
- `GET /health/ready` -> `DGW_CORE_API_BASE_URL`, `DGW_CORE_API_TOKEN` 존재 여부 확인

## 6) 슬래시 커맨드 명세

소스 기준: `codial_discord.command_specs.build_application_commands`

## 6.1 커맨드 목록

| 명령어 | 옵션 | 코어 API 연동 | 설명 |
| --- | --- | --- | --- |
| `/ask` | `text`(str, optional), `attachment`(file, optional) | `POST /v1/sessions/{id}/turns` | 턴을 큐에 넣어요. |
| `/end` | 없음 | `POST /v1/sessions/{id}/end` | 세션 종료를 요청해요. |
| `/provider` | `provider`(choice, required) | `POST /v1/sessions/{id}/provider` | 현재는 `github-copilot-sdk`만 선택 가능해요. |
| `/model` | `model`(str, required) | `POST /v1/sessions/{id}/model` | 모델 문자열을 바꿔요. |
| `/mcp` | `enabled`(bool), `profile`(str) | `POST /v1/sessions/{id}/mcp` | MCP 설정을 바꿔요. |
| `/subagent` | `name`(str, optional) | `POST /v1/sessions/{id}/subagent` | 서브에이전트를 설정/해제해요. |
| `/rules_list` | 없음 | `GET /v1/codial/rules` | CODIAL 규칙 목록을 보여줘요. |
| `/rules_add` | `rule`(str, required) | `POST /v1/codial/rules` | CODIAL 규칙을 추가해요. |
| `/rules_remove` | `index`(int>=1, required) | `DELETE /v1/codial/rules` | CODIAL 규칙을 제거해요. |
| `/규칙목록` | 없음 | `GET /v1/codial/rules` | 한국어 별칭이에요. |
| `/규칙추가` | `rule`(str, required) | `POST /v1/codial/rules` | 한국어 별칭이에요. |
| `/규칙제거` | `index`(int>=1, required) | `DELETE /v1/codial/rules` | 한국어 별칭이에요. |

참고:

- 라우터는 `서브에이전트` 명령 이름도 처리해요. 다만 자동 동기화 스펙에는 기본적으로 `/subagent`를 등록해요.

## 6.2 `start_chat` 버튼 동작

컴포넌트 `custom_id=start_chat`을 받으면 아래 순서로 진행해요.

1. 코어 API에 세션 생성 (`idempotency_key` 기반)
2. Discord 텍스트 채널 생성 (`DGW_SESSION_CHANNEL_PREFIX` + 세션 suffix)
3. 코어 API에 채널 바인딩
4. 내부 `SessionBindingStore`에 `(session_id, channel_id)` 저장
5. 채널/ephemeral 안내 메시지 전송

권한 오버라이트 기본 정책:

- 길드 전체: `SEND_MESSAGES` deny
- 요청자 유저: `SEND_MESSAGES` allow

## 7) 코어 API 연동 규약

`CoreApiClient`는 항상 아래 헤더로 호출해요.

- `Authorization: Bearer <DGW_CORE_API_TOKEN>`

타임아웃/네트워크/5xx는 재시도 없이 예외로 처리하고, 라우트에서 로그를 남겨요.

## 8) 내부 상태 저장소

`SessionBindingStore`는 인메모리예요.

- 프로세스 재시작 시 channel <-> session 매핑이 유실돼요.
- 내구성이 필요하면 Redis 같은 외부 저장소로 교체해요.

## 9) 운영 체크리스트

- `DGW_DISCORD_PUBLIC_KEY`가 정확한지 확인해요.
- Bot 권한에 채널 생성/메시지 전송 권한이 있는지 확인해요.
- `DGW_INTERNAL_EVENT_TOKEN`과 `CORE_GATEWAY_INTERNAL_TOKEN`이 일치하는지 확인해요.
- `DGW_CORE_API_TOKEN`과 `CORE_API_TOKEN`이 일치하는지 확인해요.
- 커맨드 변경 후 `codial-discord-sync-commands`를 다시 실행해요.

## 10) 트러블슈팅

## Interactions 401 (서명 실패)

- Public Key 불일치 가능성이 가장 커요.
- 프록시가 바디를 변형(압축/재인코딩)하는지 확인해요.

## 커맨드가 보이지 않아요

- `DGW_DISCORD_APPLICATION_ID`가 올바른지 확인해요.
- 길드 스코프로 먼저 동기화해요(`DGW_DISCORD_COMMAND_GUILD_ID`).
- 글로벌 커맨드는 전파 시간이 걸릴 수 있어요.

## 세션 채널이 생성되지 않아요

- 봇의 `Manage Channels` 권한을 확인해요.
- `DGW_SESSION_CATEGORY_ID`가 올바른 카테고리인지 확인해요.

## 코어 이벤트가 채널에 안 떠요

- `POST /internal/stream-events` 요청의 토큰 값을 점검해요.
- 코어 서비스의 `CORE_GATEWAY_BASE_URL`이 게이트웨이를 정확히 가리키는지 확인해요.

## 11) 개발 체크리스트

```bash
python -m ruff check .
python -m mypy .
python -m pytest
```
