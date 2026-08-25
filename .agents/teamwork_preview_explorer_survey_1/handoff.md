# Survey Explorer 1 Report: Backend, DB & Core Integrations

## 1. Observation

### 1.1 Codebase Layout & Backend Structure
The workspace root at `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req` consists of a Python FastAPI/SQLAlchemy/Strawberry GraphQL backend, a TypeScript SDK (`sdk/typescript`), SvelteKit frontend apps (`apps/web`, `packages/ui-svelte`), and an Obsidian plugin integration (`integrations/obsidian-ultradex`).

The backend architecture is structured as follows:
- **Application Entry Point**: `api/main.py:87-165` sets up FastAPI (`title="Ultradex API", version="2.0.0"`), CORS middleware, lifespan manager (`api/main.py:35-85`), routers (`/api/v1/contacts`, `/api/v1/analysis`, `/api/v1/operations`, `/api/v2/commands`, `/api/v2/job-search/commands`, `/api/v2/operations`, `/api/v2/delegations`), and GraphQL endpoint at `/api/graphql`.
- **Database Initialization & Session Lifecycle**: `core/database.py:19-75` defines `Database` which initializes legacy tables via `Base.metadata.create_all` excluding projection/command tables, and runs Alembic migrations via `core/jobsearch_migrations.py:20-29` (`run_jobsearch_migrations()`).
- **Alembic Migrations**:
  - `migrations/versions/20260723_0001_jobsearch_projections.py:47-175`: Creates `jobsearch_opportunities`, `jobsearch_applications`, `jobsearch_relationships`, `jobsearch_outreach`, and `jobsearch_projection_checkpoints`.
  - `migrations/versions/20260723_0002_jobsearch_commands.py:21-155`: Creates `jobsearch_commands`, `jobsearch_evidence_refs`, `jobsearch_approvals`, `jobsearch_lifecycle_events`, and `jobsearch_execution_receipts`.
  - `migrations/versions/20260816_0003_jobsearch_intent.py:20-55`: Creates `jobsearch_intent`.
- **Command Gateway & Dispatch**: `core/jobsearch_commands.py:212-402` (`JobSearchGatewayService`) validates commands against `COMMAND_NAMES_V1`, claims idempotency in `IdempotencyService` (`core/idempotency_service.py`), emits CloudEvents (`build_jobsearch_event`), persists to `JobSearchCommandDB` / `JobSearchLifecycleEventDB`, and publishes commands to NATS JetStream (`JobSearchTaskPublisher` in `core/jobsearch_nats.py`).
- **Executor & State Machine Engine**: `core/jobsearch_executors.py:158-540` (`JobSearchExecutor`) implements handlers for 13 commands: `workspace.initialize`, `intent.set`, `sources.ingest`, `opportunities.create`, `opportunities.score`, `applications.create`, `applications.transition`, `relationships.sync`, `outreach.prepare`, `outreach.approve`, `outreach.send`, `outreach.cancel`, `evidence.export`.
- **Scoring & Intent Matcher**: `core/jobsearch_scoring.py:167-282` (`compute_score()`, `DeterministicIntentScorer`) implements rule-based scoring matching opportunities against `IntentProjectionDB` (`INTENT_SINGLETON_ID = "intent-workspace-01"`) on role family, domain, seniority band, location/remote compatibility, and hard employer exclusions (`_match_exclusion`, `EMPLOYER_ALIAS_GROUPS`).
- **Sense Sweeps & Adapters**:
  - `core/jobsearch_sources.py:108-153`: `DexSweep` computes `compute_dex_delta` (new, changed, neglected) and stashes in `RedisSweepStash`.
  - `core/jobsearch_gmail.py:64-98`: `GmailSweep` fetches thread IDs using Google OAuth (`resolve_access_token`, `fetch_thread_ids`) for queries like `DEFAULT_GMAIL_SENSE_QUERY`.
  - `cli/sense_dex.py:89-158`: Host runner for Dex sweep.
  - `cli/sense_gmail.py:41-112`: Host runner for Gmail sense sweep.
  - `cli/mine_opportunities.py:173-329`: Clusters Dex contacts by company/headline and seeds opportunities via `opportunities.create`, scores them, and syncs relationships.
- **GraphQL Read Projections**: `api/graphql/schema.py:109-345` defines GraphQL `Query` for `opportunity`, `opportunities`, `application`, `applications`, `relationship`, `relationships`, `outreach_item`, `outreach`, `approval`, `execution_receipt`, `operation`, `operations`, and `events`.

### 1.2 Pytest Test Suite Survey
Running `PYTHONPATH=. uv run pytest` yielded:
- **255 passed, 1 failed, 1 xfailed** out of 257 collected items.
- Existing passing test suites:
  - `tests/test_jobsearch_executors.py` (25 passed): Tests command execution, state transitions, domain refusals, idempotency replay, and receipts.
  - `tests/test_jobsearch_intent.py` (12 passed): Tests `intent.set`, rescore passes, and exclusion rules.
  - `tests/test_jobsearch_scoring.py` (12 passed): Tests deterministic scoring logic and integer weight contracts.
  - `tests/test_jobsearch_command_gateway.py`, `tests/test_jobsearch_command_api.py`, `tests/test_jobsearch_command_models.py` (23 passed).
  - `tests/test_graphql_jobsearch.py` (20 passed): Tests GraphQL schema queries and pagination.
  - `tests/test_sources_dex_delta.py`, `tests/test_sources_gmail.py`, `tests/test_k0s_gmail_sense.py` (25 passed).
  - `tests/test_jobsearch_projection_repository.py` (34 passed).
  - `tests/test_auth_boundary.py`, `tests/test_command_acceptance.py`, `tests/test_idempotency_atomicity.py`, `tests/test_runtime_baseline.py` (37 passed).
- Failure Point: `tests/test_obsidian_test_vault_installer.py:185`: Failed because `scripts/create-obsidian-test-vault.sh` executed `npm run build` in `integrations/obsidian-ultradex` before plugin dependencies were installed.
- Target Acceptance Test Files Status:
  - `tests/test_jobsearch_executors.py`: **EXISTS & PASSES** (25/25)
  - `tests/test_jobsearch_profile.py`: **MISSING** (File does not exist)
  - `tests/test_jobsearch_copilot.py`: **MISSING** (File does not exist)
  - `tests/test_jobsearch_messaging.py`: **MISSING** (File does not exist)
  - `tests/test_jobsearch_calendar.py`: **MISSING** (File does not exist)
  - `tests/test_jobsearch_gjallarhorn.py`: **MISSING** (File does not exist)

---

## 2. Logic Chain: Requirement vs. Implementation Gap Analysis

### R1. Candidate Profile & Dynamic Sourcing Engine
- **Requirement**: Authoritative candidate profile store (`/profile`) seeded with Nate Walker's resume, 40+ CTO skills taxonomy (Expert/Advanced), production ML depth, target roles, and compensation expectations ($180k base / $250k target). Dynamic job sourcing in `cli/sense_jobs.py` querying profile to scrape/score target career boards (Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS).
- **Observed State**:
  - Current Intent singleton (`IntentProjectionDB` in `core/jobsearch_models.py:136-164`) stores target role families, domains, seniority, location, exclusions, and integer weights.
  - Current Intent seed in `tests/test_jobsearch_intent.py:47-99` and `cli/mine_opportunities.py:36-67` has role families and compensation notes in narrative, but lacks the structured 40+ skills taxonomy with Expert/Advanced tiers, production ML depth matrix, and dedicated profile REST/GraphQL API.
  - `cli/sense_jobs.py` does **NOT** exist in `cli/` (only `sense_dex.py`, `sense_gmail.py`, `mine_opportunities.py` exist).
  - `tests/test_jobsearch_profile.py` is absent.
- **Inference**: A profile domain model/store (`core/jobsearch_profile.py`), API endpoints (`/profile`, GraphQL `profile`), dynamic job scraper CLI (`cli/sense_jobs.py`), and test suite (`tests/test_jobsearch_profile.py`) must be built.

### R2. Complete CRM Domain & Pipeline Lifecycle
- **Requirement**: CRM domain entities with ORM models, GraphQL APIs, and pipeline lifecycles:
  - **Contacts** (`/contacts`, `/contacts/[id]`): 2,252 Dex contacts with CRM profile, advocacy score, communication history.
  - **Organizations** (`/organizations`, `/organizations/[id]`): Directory aggregating contacts, open leads, opportunities.
  - **Leads** (`/leads`, `/leads/[id]`): Unapplied postings with profile match breakdown, one-click "Apply / Convert to Opportunity".
  - **Opportunities** (`/opportunities`, `/opportunities/[id]`): Active pursuits with stage trackers and connected contacts.
  - **Applications** (`/applications`, `/applications/[id]`): Formal stage progression tracking.
  - **Relationships** (`/relationships`): Clean table (Name -> Organization -> Role -> Context).
  - Lead conversion must create an active Opportunity and initial Application record.
- **Observed State**:
  - Existing DB tables: `contacts` (`ContactDB` in `core/models.py:162-185`), `jobsearch_opportunities` (`OpportunityProjectionDB` in `core/jobsearch_models.py:46-69`), `jobsearch_applications` (`ApplicationProjectionDB` in `core/jobsearch_models.py:71-91`), `jobsearch_relationships` (`RelationshipProjectionDB` in `core/jobsearch_models.py:93-111`).
  - Missing DB tables / Models: No dedicated `OrganizationDB` or `LeadDB` tables. Organizations are implicitly strings on contacts/opportunities. Leads are currently conflated with `OpportunityProjectionDB(state='discovered')`.
  - Lead Conversion: `core/jobsearch_executors.py` has separate `opportunities.create` and `applications.create`, but no unified `leads.convert` or lead-to-opportunity+application atomic command.
  - GraphQL API (`api/graphql/schema.py:109-345`): Has queries for `opportunities`, `applications`, `relationships`, `outreach`, `operations`, but **no GraphQL queries for `contacts`, `organizations`, `leads`, or `profile`**.

### R3. Copilot Engine & Omnichannel In-App Messaging
- **Requirement**: Copilot Next Best Actions on Command Home (`/`), 3-pill recruiter reply generator (*1. Accept & Share Availability*, *2. Request Scope & Comp Details*, *3. Polite Pass*) with live Google Calendar availability injection, in-app Gmail/LinkedIn message dispatcher landing in Gmail Sent folder.
- **Observed State**:
  - Outbox state machine exists in `core/jobsearch_executors.py:922-1085` (`outreach.prepare`, `outreach.approve`, `outreach.send`, `outreach.cancel`) with `JobSearchApprovalDB`, but `_outreach_send` relies on a stub `OutreachSender` interface.
  - `core/jobsearch_gmail.py:1-223` only supports reading/sensing thread IDs via `fetch_thread_ids`. No sending mechanism via Gmail API (`users.messages.send` with RFC 2822 MIME formatting) exists.
  - No LinkedIn gateway dispatcher exists.
  - No Copilot Next Best Action scoring or recommendation engine exists in `core/`.
  - No 3-pill recruiter response generator module exists.
  - `tests/test_jobsearch_copilot.py` and `tests/test_jobsearch_messaging.py` are absent.

### R4. Google Calendar & Sovereign Voice Engine (Gjallarhorn + MQTT)
- **Requirement**: Google Calendar sensing detecting scheduled interview rounds and computing open 30-min/45-min slots during working hours (09:00–17:00 CT). Mosquitto MQTT (`ratatoskr:1883`) and Gjallarhorn ASR (`ratatoskr:18099`) integration to record/stream audio, extract structured debriefs (Executive Summary, Questions Asked, Action Items), auto-populate Command Home action items, and export formatted Markdown notes to local Obsidian vault (`~/docs/40-personal/interviews/`).
- **Observed State**:
  - Google Calendar: No calendar client or slot calculation engine in `core/`.
  - Gjallarhorn / MQTT: No MQTT subscriber (`ratatoskr:1883`), no ASR connector (`ratatoskr:18099`), and no structured debrief extraction engine in `core/`.
  - Local Obsidian Exporter: No Python backend vault exporter saving structured interview debriefs to `~/docs/40-personal/interviews/`.
  - `tests/test_jobsearch_calendar.py` and `tests/test_jobsearch_gjallarhorn.py` are absent.

---

## 3. Caveats
- **Live System Connectivity**: Investigation was conducted locally inside `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req`. Live network connectivity to external services (`ratatoskr:1883`, `ratatoskr:18099`, `10.10.20.101:30808`, Google APIs) was not verified in this offline code inspection pass.
- **Frontend Svelte App Details**: A high-level scan of `apps/web` was performed, but detailed SvelteKit component hierarchy and Glass UI contrast compliance is assigned to the frontend survey agent.
- **Package Management**: Python environment required Python 3.11 for `psycopg2-binary==2.9.9` C-extension compatibility, with `ravenhelm-contracts==0.5.0` installed from local editable repo `/Users/nate/src/hrafngud.ravenmask.net/nate/ravenhelm-contracts/jobsearch-intent`.

---

## 4. Conclusion

The core UltraDex backend has a solid event-sourcing and governed command execution foundation (`core/jobsearch_executors.py`, `core/jobsearch_commands.py`, `core/jobsearch_models.py`, `core/jobsearch_scoring.py`, `migrations/`). 255 existing backend tests pass.

However, to satisfy the full requirements in `ORIGINAL_REQUEST.md`, the following substantive components are missing and must be developed:
1. **Candidate Profile & Sourcing Engine (R1)**:
   - Module `core/jobsearch_profile.py` with Nate Walker's 40+ CTO skills taxonomy (Expert/Advanced), production ML depth, target roles, comp bounds ($180k-$250k), and profile store.
   - CLI tool `cli/sense_jobs.py` for automated job scraping across 9 target career boards.
   - Test suite `tests/test_jobsearch_profile.py`.
2. **CRM Domain & Pipeline Extension (R2)**:
   - Database models and migrations for Organizations (`OrganizationDB`) and Leads (`LeadDB`).
   - Lead conversion executor logic: converting a Lead atomically creates an active Opportunity and initial Application record.
   - GraphQL schema updates (`api/graphql/schema.py`, `api/graphql/jobsearch_types.py`) adding GraphQL types/queries for Profile, Leads, Organizations, Contacts, and Relationships.
3. **Copilot & Omnichannel Messaging Engine (R3)**:
   - Copilot engine `core/jobsearch_copilot.py` computing Next Best Actions.
   - 3-pill recruiter response generator with live Google Calendar availability slot injection.
   - Omnichannel message dispatcher (`core/jobsearch_messaging.py` / `GmailMessageDispatcher`) implementing RFC 2822 MIME generation and direct Gmail API `users.messages.send` dispatch (landing in Gmail Sent folder) plus LinkedIn gateway integration.
   - Test suites `tests/test_jobsearch_copilot.py` and `tests/test_jobsearch_messaging.py`.
4. **Google Calendar & Sovereign Voice Engine (R4)**:
   - Google Calendar engine (`core/jobsearch_calendar.py`) sensing interview rounds and computing 30/45-min open slots in Central Time (09:00–17:00 CT).
   - Voice/ASR integration (`core/jobsearch_gjallarhorn.py`) connecting to Mosquitto MQTT (`ratatoskr:1883`) and Gjallarhorn ASR (`ratatoskr:18099`), extracting structured debriefs (Summary, Questions, Action Items).
   - Obsidian exporter generating formatted interview markdown in `~/docs/40-personal/interviews/`.
   - Test suites `tests/test_jobsearch_calendar.py` and `tests/test_jobsearch_gjallarhorn.py`.

---

## 5. Verification Method

To verify these findings independently:

1. **Verify Existing Tests**:
   ```bash
   cd /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req
   PYTHONPATH=. uv run pytest tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py tests/test_graphql_jobsearch.py
   ```
2. **Verify Missing Test Files**:
   ```bash
   ls tests/test_jobsearch_profile.py tests/test_jobsearch_copilot.py tests/test_jobsearch_messaging.py tests/test_jobsearch_calendar.py tests/test_jobsearch_gjallarhorn.py
   # Confirms files do not exist (No such file or directory)
   ```
3. **Verify Missing CLI Script**:
   ```bash
   ls cli/sense_jobs.py
   # Confirms cli/sense_jobs.py does not exist
   ```
4. **Inspect DB Models & GraphQL Schema**:
   - Inspect `core/jobsearch_models.py` and `core/models.py` to confirm table definitions.
   - Inspect `api/graphql/schema.py` to confirm absence of `profile`, `contacts`, `organizations`, and `leads` queries.
