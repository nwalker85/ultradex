# CCC Current → Target Mapping (ultradex → rebuild Postgres tier)

- **Status:** Draft — a cutover artifact per ADR-0001 §"Cutover" (ADR-011 discipline). **Not** authorization to migrate, delete, or decommission anything.
- **Date:** 2026-09-03
- **Owner:** Nate Walker
- **Linear:** RAV-1673 (ratification); DDL it maps onto: RAV-1672
- **Current side:** `nate/ultradex` `main` @ `2e53356` — `core/models.py`, `core/jobsearch_models.py`, `migrations/versions/20260723_0001 … 20260827_0006` (alembic head `20260827_0006` on vakr `ccc-tmp` postgres, verified 2026-08-31).
- **Target side:** Career CRM Relational Schema Design (amended 2026-09-01) as amended by ADR-0002 (`docs/decisions/0002-ccc-scope-containment-model.md`); DDL in `docs/target-schema/sql/`.
- **Scope model reference:** ADR-0006 Identity Fabric Scope Hierarchy — Outline <https://outline.ravenhelm.dev/doc/wbhKcUoeKs>.

## 0. Ground rules for this mapping

1. Every current table and column appears below with exactly one disposition: **map** (to a target column, with transform), **provenance** (retained only as `source_records` / `source_record_versions` + a typed link), **custody** (raw private value moves to the designated custody system; CCC keeps an opaque ref + commitment), or **retire** (not carried; reason given).
2. Mimir coordinates are **never** minted by this migration. Organizations and contacts land as `resolution_status = 'unresolved'` projections with candidate evidence in provenance; resolution happens through the Phase 0/1 Mimir resolver afterwards (tenant-scope design "CCC resolver rules" 7–9).
3. Raw email, phone, LinkedIn URLs, notes, message bodies and provider ids do not enter target rows (relational spec constraint 16). They go to custody with a `value_commitment = sha256(canonical value)` so idempotent re-resolution works.
4. The `workspace_id` for every migrated row is the single operator workspace, created first and bound to scope `i/ravenhelm/t/ravenhelm/o/<org>/a/ccc/p/<workspace>` (ADR-0002 §4; org slug = operator decision).
5. Current ids (`String(64)` semantic ids like `organization-a5c26a7e-…`, `lead-83ab83f4-…`) are preserved as `source_records.external_object_ref` under `integration_accounts(provider = 'ultradex-legacy')`, never as target PKs.

## 1. Table inventory and disposition

| Current table | Rows (vakr, 2026-08-31) | Disposition | Target |
|---|---|---|---|
| `contacts` (legacy Dex projection, `core/models.py:163`) | 2,257 | map + custody + provenance | `contacts`, `contact_channels`, `contact_organization_affiliations`, `source_records(object_type='dex_contact')` |
| `jobsearch_organizations` | small (JAGGAER + backfill) | map + provenance | `organizations`, `organization_domains`, `source_records(object_type='ultradex_organization')` |
| `jobsearch_leads` | 25 mined + manual | map + provenance | `leads` (+ `employment_opportunity_details` fields on conversion) |
| `jobsearch_opportunities` | 25 | map | `opportunities` (+ type detail), `opportunity_organizations`, `opportunity_stage_history` |
| `jobsearch_applications` | few | map | `submissions(submission_type='application')`, `submission_documents` (from `artifact_refs`) |
| `jobsearch_relationships` | few | map | `opportunity_contacts` (role from relevance context; default `other`) |
| `jobsearch_outreach` | few | map (bounded) | `interactions(interaction_type per channel)` + `interaction_contacts` + `interaction_opportunities`; commitment fields preserved |
| `jobsearch_approvals` | few | provenance | `source_records(object_type='outreach_approval')`; the approval envelope itself is control-surface evidence, not CRM state |
| `jobsearch_evidence_refs` | many | provenance | `source_record_versions` (commitment + 240-char redacted summary map 1:1) |
| `jobsearch_intent` | 1 | **retire** from CRM tier | intent/weights are scoring configuration → Phase 2 `scoring_runs.model_version` input; keep a JSON export in the migration ledger |
| `jobsearch_entity_notes` | few | map (bounded) | `interactions(interaction_type='note')` with `redacted_summary`; raw `comment` → custody |
| `jobsearch_commands`, `jobsearch_lifecycle_events`, `jobsearch_execution_receipts` | many | **retain read-only** in legacy; not migrated | control-surface v1 history; ADR-0001 cutover keeps v1 queries read-only during reconciliation; export to the accountability archive |
| `jobsearch_projection_checkpoints` | 6 | retire | projector state of the legacy runtime |
| `operations`, `operation_events`, `delegations`, `idempotency_keys` | many | retain read-only in legacy | v1 runtime bookkeeping; new gateway owns its own |
| `analysis_runs` | some | retire | ad-hoc AI cost log; no target |
| `settings` | few | retire | runtime config; new service uses environment + Mimir |
| `alembic_version` | 1 | retire | target repo has its own migration lineage |

## 2. Column-level mapping

### 2.1 `contacts` (Dex projection) → contact projections

| Current column | Disposition | Target / transform |
|---|---|---|
| `id` (Dex id string) | provenance | `source_records.external_object_ref`; `external_id_commitment = sha256('dex:'||id)` |
| `name` | map (bounded) | `contacts.display_name` (trim; required — rows with empty name get `display_name = 'unknown-'||left(commitment,8)` and a `resolution_status='unresolved'`) |
| `email` | custody | `contact_channels(channel_type='email', channel_ref=<custody ref>, value_commitment=sha256(lower(trim(email))))`; raw value **not** stored |
| `phone` | custody | `contact_channels(channel_type='phone', value_commitment=sha256(e164))` |
| `linkedin_url` | custody | `contact_channels(channel_type='linkedin', value_commitment=sha256(normalized url))` |
| `company` (free text) | map via reconciliation | `contact_organization_affiliations.organization_id` after §3 reconciliation; unresolved names stay in `source_record_versions.normalized_metadata.company_name` |
| `job_title` | map | `contact_organization_affiliations.title` |
| `notes`, `crm_notes`, `communication_history` (JSON) | custody | `interactions(interaction_type='note')` one per history entry with `content_ref` + `content_commitment`; `redacted_summary` ≤ 240 chars |
| `last_contacted` | map | derived: max `interactions.occurred_at`; not stored on the projection ("latest value" fields never promote — ADR-0001 §1) |
| `ai_value`, `ai_reason`, `outreach_strategy`, `suggested_timing`, `last_analyzed` | retire | model outputs; regenerated by Phase 2 scoring (`scoring_runs`/`action_scores`) |
| `advocacy_score`, `relationship_tier` | retire (score) / map (tier → `opportunity_contacts.relationship_strength` only where an opportunity link exists) | churny fields never promote (ADR-0001 §1) |
| `organization_id` (FK → `jobsearch_organizations`, PR #31) | map | `contact_organization_affiliations.organization_id` via the org id map from §2.2 |
| `created_at`, `updated_at`, `synced_at` | map | `contacts.created_at/updated_at`; `synced_at` → `sync_runs.completed_at` of the backfill run |

### 2.2 `jobsearch_organizations` → organization projections

| Current column | Disposition | Target / transform |
|---|---|---|
| `id` | provenance | `source_records.external_object_ref` |
| `name` | map | `organizations.display_name`; also `organization_aliases(alias=name)` |
| `domain` | map | `organization_domains(domain, normalized_domain=lower(strip www.), is_primary=true)`; unique per workspace — collisions resolved by §3 |
| `industry`, `size` | map (bounded) | `organizations.redacted_summary` ("industry: …; size: …") — the spec has no dedicated columns; Mimir organization attributes on resolution |
| `advocacy_rating`, `notes` | retire / custody | rating never promotes; notes → custody |
| `source_event_id`, `source_event_position`, `projected_at` | provenance | `source_record_versions.observed_at` + `normalized_metadata` |
| `kind` | **new required** | `organizations.kind = 'company'` for all legacy rows (only kind the legacy system knew) |

### 2.3 `jobsearch_leads` → `leads`

| Current column | Disposition | Target / transform |
|---|---|---|
| `id` | provenance | `source_records(object_type='ultradex_lead')` |
| `source_board`, `external_id` | provenance | `source_records.object_type = 'job_posting:'||source_board`, `external_id_commitment` |
| `employer`, `organization_id` | map | `leads.organization_candidate_ref` = opaque ref to the org projection (resolved) or to the custody candidate (unresolved) |
| `title` | map | `leads.title` |
| `location`, `remote_type`, `salary_min/max/currency` | map on conversion | `employment_opportunity_details.location/remote_policy/compensation_min/max/currency` for converted leads; for unconverted leads kept in `source_record_versions.normalized_metadata` |
| `url` | map (public only) | `leads.public_source_url` when the board is public; otherwise custody |
| `description`, `requirements` (JSON) | custody / provenance | `content_ref` + `content_commitment` on the source-record version; `leads.redacted_summary` ≤ 240 chars |
| `fit_score`, `match_breakdown`, `risk_flags` | retire | regenerated by Phase 2 scoring |
| `state` (`discovered|…|converted`) | map | `leads.status`: discovered→`new`, triaged/nurturing→`nurturing`, qualified→`qualified`, rejected→`disqualified`, converted→`converted` (exact legacy enum to be dumped from live data before execution) |
| `converted_opportunity_id` | map | `lead_conversions` row (requires a synthetic `lead_qualification_snapshots` + `lead_booking_proofs`? **No** — see §4 gap G1) |
| `motion` | **new required** | `'w2'` for every legacy lead (legacy = employment search); contract leads did not exist |
| `source_commitment` | **new required** | `sha256(source_board||':'||external_id||':'||url)` |
| `discovered_at` | map | `created_at` of the legacy row |

### 2.4 `jobsearch_opportunities` → `opportunities` (+ details, orgs, history)

| Current column | Disposition | Target / transform |
|---|---|---|
| `id` | provenance | `source_records(object_type='ultradex_opportunity')` |
| `organization_id`, `employer_name` | map | `opportunity_organizations(role='employer', is_primary=true)` → org projection; if no org row, reconcile from `employer_name` (§3) |
| `title` | map | `opportunities.name` and `role_title` |
| `location`, `role_family` | map | `employment_opportunity_details.location`; `role_family` → `opportunities.description` prefix |
| `state` | map | `opportunities.stage_id` via the stage map (§5) + one `opportunity_stage_history(from NULL → to)` row dated `created_at`; terminal states set `closed_at` |
| `score`, `score_explanation`, `risk_flags` | retire | Phase 2 scoring |
| `evidence_refs` (JSON) | provenance | `opportunity_source_records` links to the migrated `jobsearch_evidence_refs` versions |
| `opportunity_type` | **new required** | `'employment'` for all legacy rows |
| `opened_at` | map | `created_at` |

### 2.5 `jobsearch_applications` → `submissions`

`id`→provenance; `opportunity_id`→`submissions.opportunity_id` (via id map); `state`→`submissions.status` (map table §5); `stage_history` JSON → additional `opportunity_stage_history` rows where the legacy stage is a funnel stage, else `source_record_versions`; `artifact_refs` → `submission_documents` only where a `document_versions` row can be created from an existing sha256-addressable file, else provenance; `next_action`, `next_action_deadline` → one `actions(status='ready', due_at)` + `action_opportunities`, **not** `next_best_action` (the pointer is chosen by Phase 2 scoring); `submission_type='application'`; `submitted_at = created_at`.

### 2.6 `jobsearch_relationships` → `opportunity_contacts`

`dex_contact_ref` → contact projection via the Dex id map (§2.1); `relevance_score` → `relationship_strength` (0–100 int, rounded); `relevance_reason` → `opportunity_contacts` has no text column → provenance; `role='other'` (legacy had no role); PK collision `(opportunity_id, contact_id, role)` de-duplicated keeping the latest `projected_at`.

### 2.7 `jobsearch_outreach` → `interactions`

`channel` → `interaction_type` (`email`→`email`, `linkedin`→`linkedin_message`, else `note`); `state` → `direction='outbound'` + `redacted_summary` "outreach:<state>"; `message_commitment` → `interactions.content_commitment`; `approval_contract_ref`, `sent_evidence_ref` → `content_ref` (opaque) + `interaction_source_records`; `relationship_id` → `interaction_contacts(participant_role='recipient')`; `opportunity_id` → `interaction_opportunities`; `occurred_at = updated_at`.

### 2.8 `jobsearch_evidence_refs` → `source_record_versions`

`evidence_id` → `source_records.external_object_ref` under `integration_accounts(provider=source_kind)`; `source_ref` → `content_ref`; `commitment` (71 chars, `sha256:`-prefixed) → `content_commitment` and `content_fingerprint`; `redacted_summary` → `normalized_metadata.redacted_summary`; `classification` → `normalized_metadata.classification`; `observed_at` → `observed_at`.

### 2.9 `jobsearch_entity_notes` → `interactions(note)`

`entity_type/entity_id` → link table by type (`interaction_contacts` / `interaction_opportunities` / `interaction_organizations`); `comment` → custody (`content_ref`) + 240-char `redacted_summary`; `submitted_by` → provenance; `category`, `disposition`, `assigned_to` → `normalized_metadata` on the note's source-record version.

## 3. Organization / company reconciliation rules — **OPEN (ADR-0001 open decision #3, operator-only)**

Inputs that name an organization today: `contacts.company` (free text, 2,257 rows), `jobsearch_organizations.name/domain`, `jobsearch_leads.employer`, `jobsearch_opportunities.employer_name`. Proposed rule set for Nate to accept, amend, or replace:

| Rule | Proposal | Effect |
|---|---|---|
| R1 identity key | A legacy organization row is one target `organizations` projection; a free-text company name is **never** a projection by itself | no name-only projections |
| R2 domain match | `normalized_domain` equality within the workspace ⇒ same projection (evidence, not Mimir merge proof — tenant-scope design rule 4) | merges `jobsearch_organizations` dupes by domain |
| R3 name match | Exact normalized-name equality (lowercase, strip legal suffixes `inc|llc|ltd|corp|co`, punctuation) ⇒ **candidate** only; creates `organization_aliases` on the existing projection when the alias is unique in the workspace, else leaves the contact affiliation unresolved | no destructive dedupe on names |
| R4 unmatched company text | Create an `unresolved` projection with `display_name = company`, `kind='company'`, and a provenance link; no domain | 1 projection per distinct normalized name; expected several hundred |
| R5 threshold | Migration acceptance requires ≥ 95 % of contacts with non-empty `company` to affiliate to some projection, and 0 cross-workspace or cross-domain merges | validation query V4 |
| R6 Mimir | None of the above sets `mimir_entity_id`; the Phase 1 resolver does, from `organization_domains` (public) evidence first | keeps ADR-0001 tiers honest |

Decision needed before the migration plan is written: accept R1–R6, or supply the rule set.

## 4. Gaps the target schema exposes in legacy data

| # | Gap | Proposed handling |
|---|---|---|
| G1 | `lead_conversions` requires an immutable qualification snapshot + booking proof (spec §3); legacy conversions have neither | Migrate converted legacy leads with `status='converted'` and the target opportunity, but **without** a `lead_conversions` row; record the legacy conversion as `opportunity_source_records` → the lead's source record. Note in the ledger that pre-rebuild conversions are unproven. |
| G2 | `opportunities.pipeline_id/stage_id` NOT NULL; legacy `state` strings | Stage map §5; any unmapped state → first open stage + a `note` interaction "legacy state: …" |
| G3 | `employment_opportunity_details` exactly-one rule | Create one detail row per migrated opportunity even if all fields null |
| G4 | `contact_channels` UNIQUE `(workspace_id, channel_type, value_commitment)` | Same email on two Dex contacts ⇒ keep the channel on the earlier `created_at` contact, link the other via provenance; report count |
| G5 | `document_versions.sha256` + `storage_key` required | Only artifacts that exist as files with a known hash become documents; the rest stay provenance |
| G6 | `next_best_action` one per workspace | Not migrated; first Phase 2 scoring run selects it |
| G7 | Data lost 2026-08-29 (vakr ledger rows) | Nothing to migrate; recorded in the ledger as an explicit absence |

## 5. Enum maps (to be confirmed against a live `SELECT DISTINCT state` dump before execution)

| Legacy `jobsearch_opportunities.state` / `applications.state` | Target stage `code` (seeded by `ccc_seed_career_pipeline`) |
|---|---|
| `discovered`, `researching` | `identified` |
| `applied`, `submitted` | `applied` |
| `screening`, `interviewing` | `interviewing` |
| `offer` | `offer` |
| `won`, `accepted`, `hired` | `closed_won` (terminal, outcome `won`) — **only** if an `employment_offers(status='accepted')` row can be created from evidence; otherwise `offer` + note (constraint 7) |
| `lost`, `rejected`, `withdrawn`, `closed` | `closed_lost` (terminal, outcome `lost`) with `lost_reason` = legacy state |

Stage names/probabilities are placeholders (spec non-goal); codes are stable.

## 6. Backfill and referential-integrity order

1. `workspaces` → `workspace_scope_binding_projection` (resolved binding from the Mimir registry; **blocks** everything if unavailable).
2. `integration_accounts` (`ultradex-legacy`, `dex`, `gmail`, `linkedin` as present) → `sync_runs` (one backfill run).
3. `source_records` + `source_record_versions` for every legacy row (§2.8 first, then per table) — provenance before projections.
4. `organizations` → `organization_domains` → `organization_aliases` (§3 rules).
5. `contacts` → `contact_channels` (custody refs) → `contact_organization_affiliations`.
6. `pipelines`/`pipeline_stages` seed → `opportunities` → type details → `opportunity_organizations` → `opportunity_contacts` → `opportunity_stage_history`.
7. `submissions` → `submission_documents` (where G5 allows).
8. `leads` → (no snapshots/proofs) → converted-lead provenance links (G1).
9. `interactions` (+ threads, links) from outreach/notes/history.
10. `actions` + links from `next_action` fields.
11. Typed `*_source_records` links throughout; validation queries; ledger.

## 7. Validation queries and acceptance thresholds

| # | Query | Threshold |
|---|---|---|
| V1 | count(`contacts`) = count(legacy `contacts`) | exact |
| V2 | count(`source_records` where object_type like 'dex_contact') = count(legacy contacts) | exact |
| V3 | count(`opportunities`) = count(legacy `jobsearch_opportunities`) and every one has exactly one detail row | exact |
| V4 | share of legacy contacts with non-empty `company` that have ≥ 1 affiliation | ≥ 95 % (R5) |
| V5 | zero rows in any target table containing an `@` in any text column except custody refs | 0 |
| V6 | every `leads` row with legacy state `converted` has an `opportunity_source_records` link | exact |
| V7 | `SELECT … WHERE workspace_id <> <ws>` across all tables | 0 |
| V8 | scratch restore of the target dump + re-run V1–V7 | pass |

## 8. Backup, rollback, and approval gates (ADR-0001 §7 and §"Cutover")

- Before execution: RAV-1599 pg_dump rail merged and one verified dump on andvari + scratch restore of the **legacy** DB (receipt); a dump of the target DB after migration + scratch restore (V8).
- Rollback = discard the target database; legacy is never modified by this migration (read-only source). No legacy table is dropped until the loud-decommission gate.
- Gates, each a separate Nate approval: (1) this mapping ratified incl. §3 rules; (2) data-migration plan (scripts + dry-run report on a scratch copy); (3) target authority cutover (fence v1 writers; one mutation epoch); (4) legacy decommission.
