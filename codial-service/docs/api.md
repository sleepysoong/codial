# API

Base path: `/v1`

## 인증

- `/v1/health/*`를 제외한 엔드포인트는 `Authorization: Bearer <CORE_API_TOKEN>` 헤더가 필요해요.

## 세션

- `POST /sessions` 세션 생성
- `POST /sessions/{session_id}/bind-channel` 채널 바인딩
- `POST /sessions/{session_id}/end` 세션 종료
- `POST /sessions/{session_id}/provider` 프로바이더 변경
- `POST /sessions/{session_id}/model` 모델 변경
- `POST /sessions/{session_id}/mcp` MCP 설정 변경
- `POST /sessions/{session_id}/subagent` 서브에이전트 설정/해제

## CODIAL 규칙

- `GET /codial/rules` 규칙 목록 조회
- `POST /codial/rules` 규칙 추가
- `DELETE /codial/rules` 규칙 제거

## 턴

- `POST /sessions/{session_id}/turns` 턴 제출

## 헬스체크

- `GET /health/live`
- `GET /health/ready`
