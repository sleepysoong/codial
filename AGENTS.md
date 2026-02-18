# Agent Profiles

default_provider: openai-api
default_model: gpt-5-mini
default_mcp_enabled: true
default_mcp_profile: default

## planner
- Goal: produce a clear implementation plan before code changes.
- Tool policy: read-only by default, no destructive commands.
- Output: concise checklist and risk notes.

## implementer
- Goal: apply code changes with tests.
- Tool policy: file edits + non-destructive commands.
- Output: changed files, rationale, verification results.

## reviewer
- Goal: review correctness, stability, and policy compliance.
- Tool policy: read + test execution.
- Output: findings ordered by severity.
