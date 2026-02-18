# Discord Coding Agent Platform Draft (Python, 2-Server Architecture)

## 1) Project Intent and Non-Negotiables

- Build a Discord-native coding agent platform that behaves like `gemini-cli`, `claude-code`, `opencode`, but runs through Discord channels.
- Session boundary is the Discord channel. A "Start Chat" action in a main channel creates a dedicated session channel.
- Keep provider architecture extensible, but run production with GitHub Copilot SDK only (`https://github.com/github/copilot-sdk`).
- Support multimodal inputs: text, images, files.
- Support MCP (Model Context Protocol) servers and tool calls.
- Support workspace policy and behavior files like Claude Code:
  - `AGENTS.md`
  - `RULES.md`
  - `skills/`
- Stability > performance. Production-grade error handling, retry discipline, observability, and safe defaults are mandatory.

---

## 2) Final Topology (Exactly 2 Servers)

### Server A: `discord-gateway`

- Responsibility: all Discord-facing behavior.
- Receives and verifies Discord interactions/webhooks.
- Handles Discord-specific constraints (ACK deadlines, follow-up tokens, rate limits).
- Creates and manages session channels.
- Collects message content + attachments metadata and forwards normalized requests to Server B.
- Renders streamed status/result updates back to Discord.

### Server B: `agent-core-api`

- Responsibility: orchestration and AI execution.
- Session state machine, provider routing, policy merge, MCP execution, tool orchestration.
- Handles file ingestion pipeline and artifact management.
- Emits streaming events to Server A.

### Why this split

- Discord protocol/rate-limit concerns are isolated from model/tool complexity.
- Enables independent scaling and failure isolation.
- Makes provider and MCP complexity evolvable without touching Discord boundary logic.

---

## 3) Tech Stack (Python)

- Python: `3.12+`
- API framework: `FastAPI`
- Async HTTP: `httpx`
- Queue/async jobs: `Redis + arq` (or Celery if team standard requires)
- DB: `PostgreSQL + SQLAlchemy 2.x + Alembic`
- Cache/locks: `Redis`
- Object storage: `S3` compatible
- Validation/config: `pydantic v2 + pydantic-settings`
- Logging: structured JSON (`structlog`)
- Observability: OpenTelemetry traces + Prometheus metrics
- Lint/type/test: `ruff`, `mypy`, `pytest`, `pytest-asyncio`

---

## 4) Repository Convention (proposed)

```
repo/
  services/
    discord_gateway/
      app/
      tests/
    agent_core_api/
      app/
      tests/
  libs/
    contracts/
    observability/
    common/
  docs/
  AGENTS.md
  RULES.md
  skills/
  draft.md
```

Conventions:

- Strict typing, no implicit `Any` in service layer.
- No silent exception swallowing. Every catch either:
  - retries with limits, or
  - maps to typed domain error, or
  - escalates with trace-id.
- Domain errors must be explicit and stable (`error_code` taxonomy).
- Idempotency required for all externally triggered side effects.

---

## 5) End-to-End Flow

1. User clicks `Start Chat` in main channel.
2. `discord-gateway` receives interaction, verifies signature, immediately ACK/defer.
3. `discord-gateway` requests `agent-core-api` to create a session.
4. `discord-gateway` creates dedicated channel with permission overwrites.
5. Session channel is initialized with controls (`/provider`, `/model`, `/agent`, `/skill`, `/mcp`, `/end`).
6. User sends text/image/file.
7. `discord-gateway` normalizes input, sends to `agent-core-api` as `TurnRequest`.
8. `agent-core-api` runs policy merge (`RULES.md`, `AGENTS.md`, skills), provider selection, MCP/tool execution.
9. `agent-core-api` streams structured events (`plan`, `action`, `tool_result`, `response_delta`, `final`).
10. `discord-gateway` renders updates with edit-throttle + rate-limit-safe queue.

---

## 6) Server A (`discord-gateway`) Detailed Draft

### 6.1 Core Modules

- `api/interactions.py`
  - Signature verification
  - Interaction routing (button/slash/modal)
  - 3-second-safe defer behavior
- `discord/client.py`
  - Discord REST wrapper
  - rate-limit bucket tracking
  - retry with jitter
- `services/channel_manager.py`
  - session channel creation
  - permission overwrite templates
  - archive/delete routines
- `services/message_ingest.py`
  - parse text + attachments
  - normalize to internal `TurnInput`
- `services/stream_renderer.py`
  - coalesced message edits
  - chunking for Discord limits
  - fallback to thread logs
- `adapters/core_api_client.py`
  - authenticated calls to Server B
  - idempotency keys

### 6.2 API Endpoints (Server A)

- `POST /discord/interactions`
  - Handles all Discord interactions.
  - Must always return fast ACK path.
- `POST /internal/stream-events`
  - Receives stream events from Server B (or websocket callback channel).
  - Validates event signatures/token.

### 6.3 Discord-specific Stability Rules

- Never perform heavy work inline in interaction handler.
- Always defer if downstream uncertainty > 500ms.
- All channel/message mutations queued through a single rate-limit-aware worker per guild.
- Implement dedupe on interaction IDs.
- If follow-up token expired, fallback to bot token message route with user-facing explanation.

### 6.4 Error Handling

- Discord HTTP 429: retry according to response headers + jitter.
- Discord 5xx/network: bounded retry with circuit breaker.
- Invalid signature: hard reject + security metric increment.
- Partial render failure: persist pending render task and retry, never drop final answer silently.

---

## 7) Server B (`agent-core-api`) Detailed Draft

### 7.1 Core Modules

- `api/sessions.py`
  - create/end session
  - update provider/model/agent/skill/mcp profile
- `api/turns.py`
  - submit turn request
  - cancel ongoing run
- `orchestrator/session_fsm.py`
  - states: `created -> active -> running -> waiting_input -> completed|failed|archived`
- `orchestrator/turn_executor.py`
  - async run coordination
  - timeout budgets
  - cancellation propagation
- `providers/base.py`
  - provider interface contract
- `providers/copilot_sdk.py`
  - integrate `github/copilot-sdk`
- `mcp/client.py`
  - server registry + discovery + tool calls
- `policy/loader.py`
  - load `RULES.md`, `AGENTS.md`, `skills/`
- `policy/merge.py`
  - deterministic precedence and snapshot hash
- `files/ingest.py`
  - fetch, verify, scan, store
- `events/stream_bus.py`
  - push structured progress events to Server A

### 7.2 API Endpoints (Server B)

- `POST /v1/sessions`
- `POST /v1/sessions/{session_id}/end`
- `POST /v1/sessions/{session_id}/turns`
- `POST /v1/runs/{run_id}/cancel`
- `POST /v1/sessions/{session_id}/provider`
- `POST /v1/sessions/{session_id}/policy/reload`
- `GET  /v1/health/live`
- `GET  /v1/health/ready`

### 7.3 Provider Routing Strategy

- Provider selection order:
  1. Explicit session override
  2. Agent profile default (`AGENTS.md`)
  3. Global default
- Provider failure policy:
  - transient -> retry same provider
  - auth/config error -> fail fast with operator hint
  - optional fallback provider only when policy allows

### 7.4 “Thinking Process Visibility” Policy

- Do not expose unsafe raw chain-of-thought.
- Expose structured run events:
  - `plan`
  - `action`
  - `tool_call`
  - `tool_result_summary`
  - `decision_summary`
  - `response_delta`

### 7.5 MCP Integration

- Session-bound MCP server allowlist.
- Tool risk levels (`safe`, `elevated`, `restricted`).
- `restricted` tools require explicit approval event.
- Timeouts and retries per tool call, with total run budget cap.

---

## 8) AGENTS.md / RULES.md / skills Support

### 8.1 Load Order and Precedence

1. System hard safety policy
2. Session overrides (from Discord commands)
3. Workspace `RULES.md`
4. Workspace `AGENTS.md`
5. User/global defaults

### 8.2 RULES.md Scope

- command/tool allow/deny
- coding/testing/commit conventions
- secrets handling
- output format requirements

### 8.3 AGENTS.md Scope

- agent profiles (`planner`, `implementer`, `reviewer`)
- model/provider defaults
- tool permissions and run budgets

### 8.4 Skills Spec (`skills/*.yaml`)

- `name`, `description`, `inputs_schema`, `steps`, `required_tools`, `output_schema`, `safety_level`
- versioned and validated at load time

---

## 9) Async Reliability Design (Critical)

### 9.1 Idempotency

- Every turn submission carries `idempotency_key`.
- Channel creation uses deterministic dedupe key by interaction ID.
- Tool calls include `tool_call_id` for replay safety.

### 9.2 Timeouts and Budgets

- request timeout per external dependency
- run-level total budget
- tool-level budget
- cancellation token propagated across all nested calls

### 9.3 Retry Strategy

- Exponential backoff + jitter
- only retry transient classes (`timeout`, `429`, `5xx`, network)
- never retry non-idempotent side effects without idempotency guard

### 9.4 Circuit Breakers

- per provider and per MCP server
- open on rolling failure threshold
- half-open probes with strict caps

### 9.5 Dead Letter and Recovery

- unrecoverable async jobs move to DLQ
- operator command to replay with same idempotency context

---

## 10) Error Taxonomy (Must Implement)

- `AUTH_*`: invalid keys/tokens, signature failures
- `RATE_LIMIT_*`: Discord/provider throttle events
- `TIMEOUT_*`: external/internal budget exceeded
- `PROVIDER_*`: model API/bridge failures
- `MCP_*`: tool registry/invocation errors
- `POLICY_*`: invalid rules/agents/skills
- `FILES_*`: invalid mime, oversized file, scan fail
- `INTERNAL_*`: unexpected code path

Error response contract:

- `error_code`
- `message` (safe for user)
- `trace_id`
- `retryable` (bool)
- `details` (internal, redacted)

---

## 11) Data Model (Initial)

- `sessions`
  - id, guild_id, channel_id, owner_id, status, provider, model, created_at, ended_at
- `turns`
  - id, session_id, idempotency_key, status, started_at, ended_at
- `messages`
  - id, session_id, turn_id, role, content, metadata
- `artifacts`
  - id, session_id, turn_id, kind, uri, sha256, size
- `events`
  - id, session_id, turn_id, type, payload, created_at
- `policy_snapshots`
  - id, session_id, hash, rules_source, agents_source, skills_source
- `mcp_servers`
  - id, name, endpoint, auth_ref, scope, status

---

## 12) Security and Safety Baseline

- Discord signature verification mandatory.
- Least-privilege bot permissions.
- Attachment fetch allowlist and size guard.
- Malware scanning before tool/model usage.
- Secret detection/redaction in logs and model-bound payload.
- No raw provider secrets in DB logs.
- Full audit trail for tool calls and policy changes.

---

## 13) Observability and Ops

- Correlation IDs across both servers (`trace_id`, `session_id`, `turn_id`).
- Metrics:
  - interaction ack latency
  - first-token latency
  - turn failure rate
  - retry count by dependency
  - queue depth / DLQ size
- Health checks:
  - liveness: process health
  - readiness: DB + Redis + outbound dependency probes
- Graceful shutdown:
  - stop intake
  - drain queues
  - persist in-flight state

---

## 14) Implementation Phases (Execution Plan)

### Phase 0 - Foundations

- create mono-repo skeleton for two services
- shared contracts and error model
- CI checks (`ruff`, `mypy`, `pytest`)

### Phase 1 - Discord Gateway MVP

- interaction endpoint + signature verify
- start-chat button -> session channel creation
- message ingest + forwarding to core API

### Phase 2 - Core API MVP

- session/turn APIs
- OpenAI provider + streaming
- structured progress events to gateway

### Phase 3 - Policy and Skills

- `RULES.md` and `AGENTS.md` loader + merge
- skills registry + validation

### Phase 4 - MCP + Additional Providers

- MCP registry/client + tool execution controls
- Codex bridge
- Copilot SDK adapter

### Phase 5 - Hardening

- DLQ/replay
- circuit breakers
- chaos/failure injection tests

---

## 15) Immediate Next Steps (Start Now)

1. Scaffold repository with `services/discord_gateway` and `services/agent_core_api`.
2. Define shared contracts (`TurnRequest`, `StreamEvent`, `ErrorEnvelope`).
3. Implement Discord interaction ACK/defer path with idempotency and trace IDs.
4. Implement core session/turn endpoints and stub stream pipeline.
5. Add baseline tests for timeout/retry/error mapping before provider integrations.

---

## 16) Implementation Status Update

- Two-server skeleton is implemented and runnable.
- `start_chat` button flow provisions a session channel asynchronously.
- Session commands are implemented at gateway/core boundaries:
  - `/ask`
  - `/provider`
  - `/model`
  - `/mcp`
  - `/end`
- Core turn worker now uses:
  - provider manager
  - policy loader (`RULES.md`, `AGENTS.md`, `skills/` summary)
  - structured progress events
- Provider layer now runs with `github-copilot-sdk` only.
- Slash command attachment parsing is wired from Discord payload to turn request.
- Skills loader supports Claude Code skill layout (`.claude/skills/*/SKILL.md`) and frontmatter parsing.
- MCP client follows JSON-RPC method flow (`initialize`, `tools/list`, `tools/call`).
- Quality gates are active and passing:
  - Ruff lint
  - mypy strict
  - pytest
