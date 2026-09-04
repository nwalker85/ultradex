# CCC target schema (Phase 1 data model)

## What this is

Plain PostgreSQL 16 DDL implementing the target schema in
`docs/superpowers/specs/2026-08-31-career-crm-relational-schema-design.md`
(amended 2026-09-01), with the two `docs/decisions/0002-ccc-scope-containment-model.md`
section 4 changes applied:

1. `workspace_tenant_binding_projection` is renamed
   `workspace_scope_binding_projection` and gains `organization_id`,
   `application_id`, `project_id`, `scope_key` (present exactly when
   `projection_status = 'resolved'`, same rule as `tenant_id`).
2. `organizations` and `contacts` gain `mimir_scope_key text NULL` (present
   exactly when `resolution_status = 'resolved'`).

Nothing else in the spec changes. This is a **target-schema artifact and
scratch-database proof only** -- no ORM, no Alembic migration, no Python, and
no production migration, cutover, or legacy-table mapping is authorized or
attempted here (see the spec's own "Explicit non-goals").

## Layout

```
sql/0000_prelude.sql              extensions + shared trigger functions
sql/0001_workspaces_binding.sql   workspaces, workspace_scope_binding_projection
sql/0002_identity_projections.sql organizations, contacts, and their child tables
sql/0003_funnel.sql               pipelines, pipeline_stages, opportunities, type-detail tables
sql/0004_submissions_close.sql    submissions, employment_offers, contract_agreements
sql/0005_interactions.sql         interaction_threads, interactions, calendar_events
sql/0006_provenance.sql           integration_accounts, sync_runs, source_records(_versions), *_source_records links
sql/0007_documents.sql            documents, document_versions, opportunity/submission_documents
sql/0008_leads.sql                leads and the full BANT/compensation/booking/conversion chain
sql/0009_meddpicc.sql             opportunity_qualification, qualification_evidence
sql/0010_actions_nba.sql          actions, action_* links, scoring_runs, action_scores, next_best_action
sql/0011_constraints.sql          append-only triggers, workspace-match triggers, deferred constraint triggers
sql/0012_indexes.sql              FK indexes, the spec's "Indexing baseline", partial not-deleted indexes
sql/0013_seed_pipeline.sql        ccc_seed_career_pipeline(workspace_id) function
sql/0090_rls.sql                  OPTIONAL row-level security (current_setting('ccc.workspace_id', true))
sql/9000_smoke_roundtrip.sql      acceptance script: positive round trip + 8 negative checks
scripts/apply-scratch.sh          creates a scratch DB, applies 0000-0090, runs the smoke test, drops on success
```

File numbering reflects FK dependency order, not the spec's section order:
`leads` (0008) comes after `organizations`/`contacts`/`opportunities`/
`interactions`/`source_records`/`document_versions` (0002-0007) because
`lead_conversions` and `lead_qualification_evidence` reference all of them.
`qualification_evidence` (0009) similarly follows `interactions` and
`document_versions`. One spec table (`lead_source_records`, defined in 0006
alongside its sibling provenance-link tables) has its FK to `leads` added by
an `ALTER TABLE` at the top of 0008, once `leads` exists.

## How to run

```
bash docs/target-schema/scripts/apply-scratch.sh
```

Requires a local PostgreSQL 16 reachable at `localhost:5432` where the
connecting OS user is a superuser with `CREATEDB` (as documented in the
lane brief; no password, no secrets). Override `PGHOST`/`PGPORT`/`ADMIN_DB`
env vars if needed.

The script:
1. Creates `ccc_target_scratch_<pid>`.
2. Applies `sql/000*.sql` and `sql/0090_rls.sql` in lexical order, each file
   in its own transaction (`--single-transaction -v ON_ERROR_STOP=1`).
3. Runs `sql/9000_smoke_roundtrip.sql` (its own script, NOT wrapped in
   `--single-transaction`, because it manages its own transaction
   boundaries: the positive path commits, then eight negative checks each
   run as their own autocommitted `DO` block).
4. Prints the resulting table count and the smoke test's own
   `SMOKE OK: <n> tables, <m> negative checks passed` line.
5. On success, drops the scratch database and exits 0.
6. On failure, leaves the database in place, prints its name, and exits 1.

## What it proves

- The full DDL applies cleanly, in FK-dependency order, on PostgreSQL 16.
- A lead can be qualified (4 validated BANT assessments + evidence,
  4-dimension immutable snapshot), booked (confirmed booking proof with an
  external participant), and converted into an opportunity, atomically, with
  `leads.status` transitioning to `converted` and `lead_conversions` joining
  to the resulting `opportunities` row -- the core Lead -> conversion ->
  Opportunity lifecycle in the spec's Purpose section.
- Eight specific invariants are enforced by the database itself, not just by
  application code:
  1. Cross-workspace foreign-key associations are rejected (constraint 13).
  2. A wrong-type opportunity detail row is rejected (constraint 5).
  3. A contract opportunity cannot enter a Closed Won stage without an
     executed contract agreement (constraint 8).
  4. `opportunity_stage_history` is append-only (constraint 9).
  5. A workspace cannot have a second `next_best_action` pointer
     (constraint 12).
  6. A lead conversion cannot reference a qualification snapshot that
     belongs to a different lead (constraint 20).
  7. A `resolved` contact projection cannot have a null Mimir coordinate
     (constraint 15).
  8. An `unresolved` contact projection cannot carry a Mimir coordinate
     (constraint 15).
- Row-level security (0090, optional) enables and applies cleanly without
  breaking the smoke test, because the smoke test runs as the table owner
  and RLS never restricts the owner unless `FORCE ROW LEVEL SECURITY` is
  also set (it is not).

## What it does not prove

- Nothing about the **current/legacy** CCC database, a mapping from it to
  this target schema, or any migration/backfill/cutover plan -- the spec's
  "Next design artifact" section explicitly defers all of that.
- Nothing about API, SDK, command, receipt, or privacy/custody behavior --
  this is storage-layer DDL only.
- Nothing about production Postgres configuration, backup/restore, or
  performance under real data volume; the indexing here follows the spec's
  stated baseline only, with no query-plan tuning against real data.
- Full coverage of every narrative rule in the spec. See "Not expressible as
  DDL" and "Ambiguities resolved" below for the specific gaps and choices.

## Not expressible as DDL / left to the domain transaction

- **Constraint 16** ("raw private contact values cannot appear in
  organization/contact/lead/interaction/submission/integration/qualification
  rows") is a data-content rule, not a schema-shape rule. It is satisfied by
  never defining a column capable of holding raw content (every such table
  only has `*_ref`, `*_commitment`, or `redacted_*` columns) -- there is no
  general-purpose SQL CHECK that can inspect arbitrary text and prove it
  is not a raw private value.
- **Constraint 21** ("workspace-binding and identity projections are usable
  only while their canonical resolver lineage is present and their
  freshness window is current") is partially enforced: the schema requires
  `freshness = current` whenever a projection is `resolved` (self-row
  CHECK), but "CCC cannot extend or rewrite that window locally" and
  "usable" (i.e., blocking a read/query path, not just an insert) are
  application/query-layer behaviors, not something a CHECK or trigger on
  the write path can express.
- **Lead compensation override "below-floor" direction of constraint 22**:
  the schema enforces that any *attached* override belongs to the same
  Lead/workspace, is unexpired, unsuperseded, and its
  `candidate_annual_cash`/`currency` match the snapshot (deferred trigger in
  0011), and that `candidate_annual_cash < annual_cash_floor` on the
  override row itself (immediate CHECK). It does **not** enforce "a
  below-floor snapshot *must* attach an override," because the floor value
  for a snapshot that has no override is not stored anywhere in this schema
  (it only exists on `lead_compensation_overrides.annual_cash_floor`,
  i.e., where an override was actually created) -- proving the missing case
  requires the policy engine's floor value, which lives outside CCC
  Postgres. This mirrors the spec's own text: "These constraints are
  enforced by the domain transaction plus deferred database checks."
- **"A superseding assessment... cannot create a cycle"** (spec section 3
  narrative on `lead_qualification_assessments`) is not one of the 23
  numbered "Required integrity constraints" and is not in the brief's list
  of triggers to implement; it is left unenforced at the DDL layer per the
  brief's "do not gold-plate" instruction.
- **Booking-proof retry idempotency** ("an identical identity/fingerprint
  retry returns the existing proof") is upsert/application logic, not a
  schema constraint; the schema only enforces the uniqueness that makes such
  a retry detectable (`UNIQUE(workspace_id, booking_identity_digest,
  observation_fingerprint)`).

## Ambiguities resolved

- **`leads.motion`** has no enumerated value list in the spec. The spec's
  own prose repeatedly calls the two lead types "W-2 Lead" and "contract
  Lead" (in the `lead_qualification_snapshots` discussion), so `motion` is
  closed to `'w2'` and `'contract'` rather than mirroring
  `opportunities.opportunity_type`'s `'employment'`/`'contract'`
  vocabulary.
- **`organizations`/`contacts.resolution_status = 'disputed'` or
  `'retired'`**: the spec states the required-fields rule only for
  `resolved`, and the null-coordinate rule only for `unresolved`/
  `ambiguous`. `disputed`/`retired` rows are left unconstrained on the
  coordinate/resolution fields (a previously-resolved entity plausibly
  keeps its coordinate after being disputed or retired).
- **Partial-unique "one primary" indexes**: the spec explicitly states this
  rule only for `opportunity_organizations` ("A partial unique index
  permits at most one primary organization per opportunity and role").
  `opportunity_contacts`, `organization_domains`, and `contact_channels`
  also carry `is_primary` but have no equivalent explicit sentence, so no
  extra partial-unique index was added for those, per the "smallest
  defensible change" instruction.
- **`ccc_seed_career_pipeline` stage names**: the spec's own "Explicit
  non-goals" list "exact stage names or probability values" as out of
  scope, so the seeded stage codes/names (`new`, `contacted`, `qualifying`,
  `submitted`, `interviewing`, `offer`, `closed_won`, `closed_lost`) are
  explicitly placeholders, called out as such in the function's own
  comment.
- **GIN indexes**: the baseline says "GIN only for bounded JSONB fields with
  demonstrated query requirements." No such requirement is demonstrated
  anywhere in this design artifact, so none was added (`score_components`
  and `normalized_metadata` remain plain `jsonb` with no GIN index).

## Scope model reference

The `workspace_scope_binding_projection` and the `mimir_scope_key` columns implement ADR-0002 (`docs/decisions/0002-ccc-scope-containment-model.md`), which conforms to **ADR-0006 Identity Fabric Scope Hierarchy & Containment Model** — <https://outline.ravenhelm.dev/doc/wbhKcUoeKs> (`installation -> tenant -> organization -> {org.*, app.*}`; CCC workspace = `app.project` under application `ccc`; URL namespace `/t/{org}/p/{project}/app/{app}`).
