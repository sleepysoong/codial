# codial-service

Codial 코어 API 런타임 폴더예요.

## 실행

```bash
python -m pip install -e .
codial-service-dev
```

## 환경 변수

- 기본 템플릿: `.env.example`
- 실제 실행 파일: `.env`

주요 키:

- `CORE_ENABLED_PROVIDER_NAMES`: 기본값 `github-copilot-sdk`
- `CORE_COPILOT_BRIDGE_BASE_URL`: Copilot 브리지 주소
- `CORE_COPILOT_AUTH_CACHE_PATH`: 로그인 캐시 파일 경로
