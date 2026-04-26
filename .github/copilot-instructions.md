# Copilot Instructions

Repository instructions for Copilot and AI agents in PR/review context.

## Review priorities (in order)

1. **Behavioral correctness of sync logic**
   - Validate changes to ownership, reaping, and reconciliation logic (`globalList`, `globalLastSeen`, `handleList`, `sync_once`).
   - Flag any path that could cause accidental mass add/remove behavior.
   - Pay close attention to tuple mapping semantics:
     - A record is `(domain, target)`.
     - IPv4 targets map to Pi-hole hosts endpoints.
     - Non-IPv4 targets map to Pi-hole CNAME endpoints.

2. **Safety and failure handling**
   - Ensure API failures do not silently corrupt managed state.
   - Ensure auth/session handling changes do not break startup or leave invalid assumptions.
   - Flag weak error handling around JSON parsing, network responses, and state-file I/O.

3. **State persistence and upgrade compatibility**
   - Changes to persisted state format must remain backward compatible or include an explicit migration strategy.
   - Review for data-loss risks in `readState`/`flushList`.

4. **Operational ergonomics**
   - Respect current CLI and env contract (`--run-once`, `--no-remove`, `REAP_SECONDS`, `STATE_FILE`, etc.).
   - Avoid introducing behavior that would require users to change existing deployment manifests unless documented.

5. **Release and labeling hygiene**
   - If PR labels affect release notes/version bumping, ensure labels align with `.github/release-drafter.yml`.
   - Workflow edits under `.github/workflows/` should be reviewed for unintended publishing/release side effects.

## What good PRs should include

- Tests for changed behavior, especially around:
  - add/remove/sync decisions,
  - reaping window behavior,
  - `--no-remove` safeguards,
  - state parsing/persistence edge cases.
- Clear explanation of **why** behavior changed and expected operator impact.
- Backward-compatibility notes for config/state/workflow changes.

## Out of scope for automated reviews

- Do not suggest replacing project docs with generated boilerplate.
- Do not require a full local environment setup guide in each PR.
- Do not optimize for style-only changes when no behavior/risk improvement exists.
