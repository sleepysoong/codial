# Codial (Discord Coding Agent)

Codial은 2개 서버로 동작하는 디스코드 코딩 에이전트 플랫폼이에요.

- `codial-service`: 세션/워커/정책/프로바이더/MCP를 처리하는 코어 API예요.
- `codial-discord`: Discord Interactions를 받아 `codial-service` REST API를 호출하는 봇 게이트웨이예요.

현재 기본 운영 프로바이더는 `github-copilot-sdk`만 활성화되어 있어요. 다만 코드 구조는 멀티 프로바이더 확장을 고려해 유지해요.

## 디렉토리 구조

```text
.
├─ codial-service/
│  ├─ pyproject.toml
│  ├─ .env
│  ├─ .env.example
│  └─ codial_service/
│     ├─ cli.py
│     └─ app/
├─ codial-discord/
│  ├─ pyproject.toml
│  ├─ .env
│  ├─ .env.example
│  └─ codial_discord/
│     ├─ cli.py
│     └─ app/
├─ libs/
└─ .claude/
```

`codial-service`와 `codial-discord`에 실제 앱 소스까지 이동해서, 실행/환경/코드 경계를 완전히 분리했어요.

## 빠른 시작

### 1) 의존성 설치

루트 기준으로 실행해요.

```bash
python -m pip install -e ".[dev]"
python -m pip install -e "./codial-service[dev]"
python -m pip install -e "./codial-discord[dev]"
```

### 2) 환경 변수 파일 준비

각 폴더에서 `.env.example`을 참고해 `.env`를 채워요.

- `codial-service/.env`
  - `CORE_COPILOT_BRIDGE_BASE_URL`은 필수예요.
  - 기본값으로 `CORE_ENABLED_PROVIDER_NAMES=github-copilot-sdk`가 설정되어 있어요.
- `codial-discord/.env`
  - `DGW_DISCORD_PUBLIC_KEY`, `DGW_DISCORD_BOT_TOKEN`을 반드시 채워요.
  - `DGW_CORE_API_BASE_URL`은 기본값으로 `http://localhost:8081`을 사용해요.

### 3) 서비스 실행

코어 서비스를 먼저 실행해요.

```bash
cd codial-service
codial-service-dev
```

그다음 디스코드 게이트웨이를 실행해요.

```bash
cd codial-discord
codial-discord-dev
```

## Copilot 로그인 동작

`codial-service`가 시작되면 Copilot 인증 토큰을 아래 순서로 확보해요.

1. `CORE_COPILOT_BRIDGE_TOKEN` 환경 변수
2. 캐시 파일 (`CORE_COPILOT_AUTH_CACHE_PATH`, 기본 `.runtime/copilot-auth.json`)
3. 브리지 로그인 엔드포인트 호출 (`CORE_COPILOT_LOGIN_ENDPOINT`, 기본 `/v1/auth/login`)

로그인 성공 시 토큰을 캐시에 저장하고, 이후 재시작 때 재사용해요.

## codial-discord가 codial-service를 호출하는 방식

`codial-discord`는 아래 REST API를 사용해요.

- `POST /v1/sessions`
- `POST /v1/sessions/{session_id}/bind-channel`
- `POST /v1/sessions/{session_id}/turns`
- `POST /v1/sessions/{session_id}/provider`
- `POST /v1/sessions/{session_id}/model`
- `POST /v1/sessions/{session_id}/mcp`
- `POST /v1/sessions/{session_id}/subagent`
- `POST /v1/sessions/{session_id}/end`
- `GET/POST/DELETE /v1/codial/rules`

## 디스코드 명령어 동작

- `/ask`: 현재 세션 채널에서 요청을 보낼 때 사용해요.
- `/end`: 세션을 종료해요.
- `/provider`: 세션 프로바이더를 바꿔요.
  - 현재 런타임 정책상 `github-copilot-sdk`만 허용해요.
- `/model`: 모델 이름을 바꿔요.
- `/mcp`: MCP 활성/비활성과 프로필을 바꿔요.
- `/subagent` 또는 `/서브에이전트`: 서브에이전트를 설정/해제해요.
- `/규칙목록`, `/규칙추가`, `/규칙제거`: `CODIAL.md` 규칙을 관리해요.

## Discord 앱 세팅 가이드

1. Discord Developer Portal에서 애플리케이션/봇을 생성해요.
2. Interaction Endpoint URL을 `https://<gateway-host>/discord/interactions`로 설정해요.
3. 필요한 Slash Command를 등록해요.
4. `DGW_DISCORD_PUBLIC_KEY`, `DGW_DISCORD_BOT_TOKEN`을 `.env`에 반영해요.
5. 봇에 채널 생성/메시지 전송 권한을 부여해요.

## 품질 검사

```bash
python -m ruff check .
python -m mypy .
python -m pytest
```

## 참고 문서

- 설계 초안: `draft.md`
- 프로젝트 기본 규칙: `RULES.md`
- 에이전트 기본값: `AGENTS.md`
- 세션 유지용 지침: `PROJECT.md`
