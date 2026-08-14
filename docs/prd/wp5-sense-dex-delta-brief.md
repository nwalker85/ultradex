# WP5 Brief — Dex-Delta Sense Adapter (Sense #1)

**Authority:** ADR-014 (Accepted 2026-08-05, amended) → PRD F4 ("One ambient Sense source
feeds Stage with provenance") → this brief. PRD reserved the source pick for the WP brief:
**scheduled Dex delta** chosen 2026-08-14 (Gmail deferred to Sense #2 — OAuth ceremony is
not tonight's lightbulb).

## Shape (no contract changes)

`sources.ingest` is already in `COMMAND_NAMES_V1`; `SOURCE_KINDS_V1` already contains
`"dex"`; the executor's `sources.ingest` handler exists and fails closed with
`DomainRefusal("source_adapter_unbound")`. This WP implements and binds the adapter the
contract anticipated:

- `core/jobsearch_sources.py` — `DexDeltaSourceAdapter` implementing
  `SourceAdapter.ingest(command) -> EvidenceIngestResult`
- Binding at executor construction (`core/jobsearch_worker.py:145` — currently no
  `source_adapter=` kwarg → currently unbound)

## Delta semantics

One sweep = one evidence deposit. The adapter:

1. Fetches live contacts via existing `DexClient.fetch_all_contacts()`
2. Diffs against the local `contacts` table (already synced; 2,242 rows live):
   - **new** — in Dex, not local
   - **changed** — field drift on (name, email, phone) canonical fields
   - **neglected** — last-interaction beyond threshold (align with `neglected/list` logic)
3. Builds the delta payload, canonicalized (sorted keys, no whitespace)

## Provenance (F4) — the part that makes it AAL, not a cron job

- `source_ref` = `dex-sweep:<YYYYMMDD>:<digest12>` (conforms to `OPAQUE_REFERENCE_PATTERN_V1`)
- `commitment` = `sha256:<hex>` of the canonical payload (conforms to `DIGEST_PATTERN_V1`)
- `observed_at` = sweep time, ISO-8601 Z
- `redacted_summary` = **counts only** ("dex sweep: N new, M changed, K neglected") — no
  names, no emails, no PII. `classification="private"` is enforced by the handler.
- Echo-back invariant: `source_kind` / `source_ref` / `observed_at` must equal the command
  parameters or the handler refuses (`source_result_mismatch`) — the command carries the
  claim, the adapter proves it.

## Idempotency

Same delta set → same canonical payload → same digest → same `source_ref` and
`evidence_id`. A re-run with no changes deposits nothing new. An empty delta is a valid
sweep (evidence of quiet), controlled by a `deposit_empty` flag — default **false** for
tonight.

## Out of scope

Scheduler wiring (manual trigger tonight; n8n is the trigger plane later — NOT cron),
Gmail sense, auto-promotion, any Stage schema change, any contract change.

## Acceptance (curl + eyes)

1. `pytest` — adapter unit tests green, executor binding test green
2. POST `sources.ingest` (source_kind=dex) against the live stack → `evidence_id` returned
3. Row in `jobsearch_evidence_refs` with commitment + redacted summary, verified in psql
4. Re-run with no Dex changes → no duplicate evidence
5. Execution receipt row exists for the command
