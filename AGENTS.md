# AGENTS — ultradex

Forgejo-primary: `nate/ultradex`. Never push `main`; never merge without Nate's
explicit approval of that PR.

## CCC glass

- Career Director product is **`apps/web`** (Svelte local container), not Obsidian.
- UI primitives: workspace package `@ravenhelm/ui-svelte` (canonical tree also at
  `~/src/platforms/ravenhelm/libraries/ravenhelm-ui-svelte`).
- Obsidian plugin path is **deprecated** — see `integrations/obsidian-ultradex/DEPRECATED.md`.
- ML stays on Python workers; do not add ML libraries to the glass.

## Mail corpus (private Stage)

- `core/mail_*.py` + `cli/ingest_mail_corpus.py` are the **private** Gmail →
  ClickHouse Stage. Plaintext bodies live there; the governed
  `jobsearch_evidence_refs` plane still carries only a commitment plus a
  240-char redacted summary and must stay that way.
- ClickHouse credentials have **no default**. `MAIL_CLICKHOUSE_USER` /
  `MAIL_CLICKHOUSE_PASSWORD` are required, because the `default` user on vakr
  reaches every database on that host including `forensics`. Do not add a
  default; the scoped-user decision is Nate's.
- Runbook: `docs/mail-corpus-ingest.md`. Design:
  `~/docs/30-projects/career-command-center/DESIGN-mail-corpus-clickhouse.md`.

## Doctrine

ADR-014 (+ amendment local Svelte glass) under
`~/docs/30-projects/career-command-center/`.
