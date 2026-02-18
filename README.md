# Codial

Codial은 Discord 기반 코딩 에이전트 플랫폼이에요. 런타임은 아래 2개 서비스로 분리되어 있어요.

- `codial-service`: 세션/정책/워커/프로바이더/MCP를 처리하는 코어 API예요.
- `codial-discord`: Discord Interactions를 처리하고 `codial-service` REST API를 호출하는 게이트웨이 봇이에요.

현재 운영 프로바이더는 `github-copilot-sdk`만 활성화되어 있어요. 코드 구조는 멀티 프로바이더 확장을 전제로 유지해요.

## Quick Start

1) 의존성을 설치해요.

```bash
python -m pip install -e ".[dev]"
python -m pip install -e "./codial-service[dev]"
python -m pip install -e "./codial-discord[dev]"
```

2) 환경 변수를 준비해요.

- `codial-service/.env.example` -> `codial-service/.env`
- `codial-discord/.env.example` -> `codial-discord/.env`

3) 코어 API를 실행해요.

```bash
cd codial-service
codial-service-dev
```

4) Discord 게이트웨이를 실행해요.

```bash
cd codial-discord
codial-discord-dev
```

5) Discord 슬래시 커맨드를 동기화해요.

```bash
cd codial-discord
codial-discord-sync-commands
```

## 문서 안내

- 코어 API 상세 명세: `codial-service/README.md`
- Discord 봇/세팅/명령어 상세: `codial-discord/README.md`
- 정책/기본값: `RULES.md`, `AGENTS.md`, `PROJECT.md`
