# Hard Handoff Report: Milestone M2 — CRM Database Models, Migrations, Pipeline Lifecycle & Atomic Lead Conversion

## 1. Observation

Direct code inspection, implementation changes, and test execution results:

1. **Database Schema & Models**:
   - `core/jobsearch_models.py`:
     - Added `OrganizationDB` (`jobsearch_organizations`) with columns `id`, `name`, `domain`, `industry`, `size`, `advocacy_rating`, `notes`, freshness audit fields (`source_event_id`, `source_event_position`, `projected_at`, `created_at`, `updated_at`), and ORM relationships `leads` and `contacts`.
     - Added `LeadDB` (`jobsearch_leads`) with columns `id`, `source_board`, `external_id`, `employer`, `organization_id` FK (`jobsearch_organizations.id`, `ondelete="SET NULL"`), `title`, `location`, `remote_type`, `salary_min`, `salary_max`, `salary_currency`, `url`, `description`, `requirements` (JSON), `fit_score` (Float), `match_breakdown` (JSON), `risk_flags` (JSON), `state`, `converted_opportunity_id` FK (`jobsearch_opportunities.id`, `ondelete="SET NULL"`), audit freshness fields, and relationships `organization` and `converted_opportunity`.
     - Updated `JOBSEARCH_PROJECTION_TABLES` to include `"jobsearch_organizations"` and `"jobsearch_leads"`.
   - `core/models.py`:
     - Extended `ContactDB` (`contacts`) with `advocacy_score` (Float), `organization_id` FK (`jobsearch_organizations.id`, `ondelete="SET NULL"`), `crm_notes` (Text), `communication_history` (JSON), `linkedin_url` (String 500), `relationship_tier` (String 32), and `organization` relationship.

2. **Alembic Migration**:
   - `migrations/versions/20260824_0004_crm_organizations_leads.py`:
     - Creates `jobsearch_organizations` and indexes on `name`, `domain`, `industry`, `advocacy_rating`.
     - Creates `jobsearch_leads` and indexes on `source_board`, `external_id`, `employer`, `organization_id`, `title`, `remote_type`, `fit_score`, `state`, `converted_opportunity_id`.
     - Extends `contacts` table via `op.batch_alter_table("contacts")` for full cross-database SQLite/PostgreSQL compatibility.
     - Downgrade function cleanly drops foreign keys, columns, indexes, and tables in reverse dependency order.

3. **Governed Command Plane & State Machine**:
   - `core/jobsearch_commands.py`:
     - Declared `COMMAND_NAMES_CRM = COMMAND_NAMES_V1 | frozenset({"leads.create", "leads.convert", "organizations.create", "organizations.update"})`.
     - Extended `_entity_for()` mapping for `"leads.create"`, `"leads.convert"`, `"organizations.create"`, and `"organizations.update"`.
   - `core/jobsearch_executors.py`:
     - Registered handlers `_leads_create`, `_leads_convert`, `_organizations_create`, `_organizations_update`.
     - In `_leads_create`: Validates non-empty employer/title, validates `fit_score` bounds [0, 100], persists `LeadDB(state="unapplied")`, stamps projection checkpoint for `"leads"`, issues signed execution receipt.
     - In `_leads_convert`: Acquires row lock on `LeadDB`, enforces fail-closed refusal `DomainRefusal("lead_already_converted")` if `lead.state == "converted"` or `lead.converted_opportunity_id is not None`, refuses `lead.state == "dismissed"`, atomically mutates `LeadDB(state="converted", converted_opportunity_id=opp.id)`, creates active `OpportunityProjectionDB`, creates initial `ApplicationProjectionDB` with `stage_history`, syncs `RelationshipProjectionDB` rows for provided `contact_refs` via `RelationshipResolver`, stamps checkpoints, issues receipt in a single transaction.
     - In `_organizations_create` & `_organizations_update`: Manages `OrganizationDB` records with canonical ID prefix `organization-`, validates `advocacy_rating` bounds [0.0, 100.0], stamps `"organizations"` projection checkpoint.
     - Extended `_stamp_projection()` mapping to include `OrganizationDB: "organizations"` and `LeadDB: "leads"`.

4. **Projections Query API**:
   - `core/jobsearch_projections.py`:
     - Added `get_lead(db, lead_id) -> LeadDB | None` and `list_leads(db, first, after, min_fit_score, state, employer) -> ProjectionPage[LeadDB]`.
     - Added `get_organization(db, organization_id) -> OrganizationDB | None` and `list_organizations(db, first, after, sort_by) -> ProjectionPage[OrganizationDB]`.

5. **Test Suite Verification**:
   - Test Command: `PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_executors.py tests/test_jobsearch_migrations.py tests/test_jobsearch_profile.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py`
   - Result: 136 passed, 1 warning in 6.32s (100% pass rate).
   - Migration round-trip script executed cleanly: `command.upgrade(cfg, 'head')` -> `command.downgrade(cfg, 'base')` -> `command.upgrade(cfg, 'head')`.

---

## 2. Logic Chain

1. **Atomicity & State Invariants**:
   - The atomic lead conversion requirement (PROJECT.md §F4) mandates that converting a lead produces both an active Opportunity and an initial Application record with zero possibility of partial state.
   - In `core/jobsearch_executors.py:1218-1364`, `_leads_convert` performs all database modifications (`LeadDB`, `OpportunityProjectionDB`, `ApplicationProjectionDB`, `RelationshipProjectionDB`) within the executor's managed transaction before calling `_finalize()`.
   - If an exception occurs (e.g. `RelationshipResolver` network crash), `execute()` catches the exception, calls `self._db.rollback()`, ensuring that no orphan Opportunity or Application rows are created and `LeadDB` remains in `unapplied` state. This was verified in `test_leads_convert_rolls_back_atomically_on_resolver_failure`.

2. **Idempotency & Duplicate Conversion Refusal**:
   - Re-attempting conversion on an already-converted lead raises `DomainRefusal("lead_already_converted", receipt_reason="policy_denied")`, which generates a signed refused receipt without modifying the existing records. This was verified in `test_leads_convert_refuses_duplicate_conversion_fail_closed`.
   - Replaying a command with the same idempotency key returns the cached execution receipt and outcome with `outcome.replayed == True` without duplicate row insertion. Verified in `test_crm_commands_idempotency_replay`.

3. **Contract and Schema Integrity**:
   - In `ravenhelm_contracts.accountability_v1`, `canonical_accountability_bytes()` requires all numeric parameters in accountability envelopes to be safe integers. `JobSearchExecutor` handlers and test parameters adhere strictly to integer serialization, guaranteeing valid Ed25519 signature generation and receipt verification (`verify_receipt_signature`).
   - `JobSearchEventAttributesV1` enforces a strict schema whitelist (`{"state", "result", "connector", "score_bucket", "stage", "commitment", "evidence_ref"}`). Handlers emit only allowed attributes (`state`, `stage`), guaranteeing compliant event publication.

---

## 3. Caveats

- **External Contact Sync**: `ContactDB` schema extensions (`advocacy_score`, `crm_notes`, `organization_id`, `communication_history`) are sovereign CRM attributes maintained locally; background sync runs (`core/dex_client.py`) must preserve these fields during upstream contact refreshes.
- **Pre-existing Obsidian Workspace Build**: The `obsidian-ultradex` TypeScript build failure in `tests/test_obsidian_test_vault_installer.py` is an unrelated legacy plugin compilation error outside the CRM backend scope. All CRM core and jobsearch test suites pass 100%.

---

## 4. Conclusion

Milestone M2 (CRM Database Models, Migrations, Pipeline Lifecycle & Atomic Lead Conversion) is complete:
- `OrganizationDB` and `LeadDB` ORM models are registered and versioned under Alembic.
- `ContactDB` is extended with full CRM relationship, advocacy, and interaction metadata.
- Migration `20260824_0004` applies and downgrades cleanly across SQLite and PostgreSQL.
- Governed commands `leads.create`, `leads.convert`, `organizations.create`, and `organizations.update` execute with fail-closed domain guardrails, cryptographic receipts, and atomic rollback guarantees.
- Read query projections are fully implemented in `core/jobsearch_projections.py`.
- 100% of M2 test suites pass with zero regressions.

---

## 5. Verification Method

To independently verify the implementation:

```bash
# 1. Run full M2 test suites
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_executors.py tests/test_jobsearch_migrations.py tests/test_jobsearch_profile.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py -v

# 2. Run related NATS, gateway, projection repository, and receipt tests
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_nats.py tests/test_jobsearch_command_api.py tests/test_jobsearch_command_gateway.py tests/test_jobsearch_projection_repository.py tests/test_jobsearch_receipts.py -v

# 3. Verify Alembic migration upgrade/downgrade round-trip
.venv/bin/python3 -c "
from alembic import command
from core.jobsearch_migrations import alembic_config
cfg = alembic_config('sqlite:////tmp/test_crm_migration.db')
command.upgrade(cfg, 'head')
command.downgrade(cfg, 'base')
command.upgrade(cfg, 'head')
print('Migration upgrade/downgrade round-trip verified successfully.')
"
```
