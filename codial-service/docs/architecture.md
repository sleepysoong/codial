# Architecture

`codial-service`는 모듈형 모놀리식 구조를 사용해요.

핵심 원칙:

- 기능(Feature) 단위로 API를 분리해요.
- 조립(Bootstrap)과 비즈니스 로직을 분리해요.
- 서비스 인스턴스는 시작 시 한 번만 만들고 `app.state`에 주입해요.

## 디렉터리 트리

```text
codial_service/
├── app/
│   ├── main.py                  # FastAPI 엔트리포인트
│   ├── routes.py                # 하위 호환용 라우터 alias
│   └── ...                      # 기존 도메인/인프라 모듈
├── bootstrap/
│   ├── container.py             # 런타임 구성요소 조립
│   └── lifespan.py              # app.state 주입 + 시작/종료 수명주기
└── modules/
    ├── common/
    │   └── deps.py              # 인증/의존성 조회 공통 함수
    ├── sessions/
    │   ├── api.py               # 세션 API 엔드포인트
    │   └── service.py           # 세션 유스케이스 조합
    ├── turns/
    │   ├── api.py               # 턴 제출 API
    │   ├── service.py           # 턴 제출 유스케이스
    │   ├── worker.py            # 워커 풀 실행 루프
    │   └── engine.py            # 턴 처리 오케스트레이션
    ├── rules/
    │   └── api.py               # CODIAL 규칙 API
    └── health/
        └── api.py               # 헬스체크 API
```

## 요청 흐름

1. `app/main.py`가 FastAPI 앱을 만들고 `modules` 라우터를 등록해요.
2. `bootstrap/lifespan.py`가 시작 시 `bootstrap/container.py`로 컴포넌트와 서비스를 1회 조립해요.
3. `modules/*/api.py`는 인증/HTTP 매핑만 담당하고, 실제 유스케이스는 `app.state`의 서비스에 위임해요.
4. 턴 처리 요청은 `TurnWorkerPool` 큐로 전달되고, `TurnEngine`이 실제 턴 오케스트레이션을 수행해요.

## 하위 호환성

- 기존 import 경로 `codial_service.app.routes.router`는 유지돼요.
- 기존 import 경로 `codial_service.app.session_service.SessionService`는 유지돼요.
- 내부 구현은 `codial_service.modules.build_api_router()`로 조립해요.
