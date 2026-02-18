# codial-discord

Codial Discord 게이트웨이 런타임 폴더예요.

## 실행

```bash
python -m pip install -e .
codial-discord-dev
```

## 슬래시 커맨드 동기화

Discord 앱에 커맨드를 일괄 등록하거나 갱신할 때 아래 명령을 실행해요.

```bash
codial-discord-sync-commands
```

`DGW_DISCORD_COMMAND_GUILD_ID`가 비어 있으면 글로벌 커맨드로 동기화하고, 값이 있으면 해당 길드에 빠르게 동기화해요.

## 환경 변수

- 기본 템플릿: `.env.example`
- 실제 실행 파일: `.env`

주요 키:

- `DGW_DISCORD_PUBLIC_KEY`
- `DGW_DISCORD_BOT_TOKEN`
- `DGW_DISCORD_APPLICATION_ID`
- `DGW_DISCORD_COMMAND_GUILD_ID`
- `DGW_CORE_API_BASE_URL`
