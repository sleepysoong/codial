# codial-service

`codial-service`는 Codial의 코어 API 서비스예요.

- 세션 상태 관리
- 턴 큐/워커 처리
- 프로바이더 브리지 호출
- MCP 연동
- CODIAL 규칙 관리

## 문서

- 아키텍처: `docs/architecture.md`
- API: `docs/api.md`
- 운영/실행: `docs/operations.md`

## 현재 구조 (요약)

```text
codial_service/
├── app/
│   ├── main.py
│   ├── routes.py
│   └── ...
├── bootstrap/
│   ├── container.py
│   └── lifespan.py
└── modules/
    ├── common/
    ├── sessions/   # api.py + service.py
    ├── turns/      # api.py + service.py + worker.py + engine.py
    ├── rules/
    └── health/
```

`app/routes.py`는 하위 호환을 위한 alias이고, 실제 라우팅 조립은 `modules`를 사용해요.

## 실행

```bash
python -m pip install -e .
codial-service-dev
```

## 테스트

```bash
python -m pytest tests/ -v
```
