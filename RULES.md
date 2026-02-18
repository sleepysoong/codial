# Global Rules

## Stability First
- Favor reliability over speed.
- Do not silently swallow exceptions.
- Every external call needs timeout + retry policy.

## Security
- Never log raw secrets.
- Validate and sanitize file uploads before use.
- Enforce least privilege for Discord and MCP tools.

## Coding
- Keep strict typing and predictable interfaces.
- Add tests for retry, timeout, and error mapping paths.
- Keep domain errors explicit and stable.
