# AGENTS.md

Repository instructions for AI agents writing and modifying code.

## What this project is optimizing for

- Keep DNS sync behavior predictable and safe for home/self-hosted operators.
- Prefer correctness and data safety over clever refactors.
- Minimize surprise deletions in Pi-hole.
- Preserve compatibility with Pi-hole v6 API behavior used by `shim.py`.

## Core implementation constraints

- Treat tuple mapping semantics as invariant:
  - A record is `(domain, target)`.
  - IPv4 targets map to Pi-hole hosts endpoints.
  - Non-IPv4 targets map to Pi-hole CNAME endpoints.
- Respect current CLI and env contract (`--run-once`, `--no-remove`, `REAP_SECONDS`, `STATE_FILE`, etc.).
- Avoid introducing behavior that requires deployment manifest changes unless explicitly documented.

## Style and scope guidance for agents

- Keep changes focused; avoid broad rewrites unless explicitly requested.
- Do not add new runtime dependencies without strong justification.
- Preserve existing public-facing env vars/flags where possible.
- Prefer small, test-backed fixes over architectural churn.

## Security and secrets

- Never commit secrets (tokens, passwords, `.env` values).
- Do not log sensitive values.
- Treat `PIHOLE_TOKEN` handling as security-sensitive.
