# Operations

## 실행

```bash
python -m pip install -e .
codial-service-dev
```

프로덕션 모드:

```bash
codial-service
```

## 테스트

```bash
python -m pytest tests/ -v
```

## 주요 환경 변수 (`CORE_*`)

- `CORE_HOST`, `CORE_PORT`
- `CORE_API_TOKEN`
- `CORE_GATEWAY_BASE_URL`, `CORE_GATEWAY_INTERNAL_TOKEN`
- `CORE_TURN_WORKER_COUNT`
- `CORE_DEFAULT_PROVIDER_NAME`, `CORE_ENABLED_PROVIDER_NAMES`
- `CORE_COPILOT_BRIDGE_BASE_URL`, `CORE_COPILOT_BRIDGE_TOKEN`
- `CORE_MCP_SERVER_URL`, `CORE_MCP_SERVER_TOKEN`
- `CORE_WORKSPACE_ROOT`

상세 기본값은 `codial_service/app/settings.py`를 기준으로 관리해요.
