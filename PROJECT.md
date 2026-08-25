# Project: Career Command Center (CCC) Job-Search CRM & Operating System

## Architecture
Career Command Center is a mission-critical, sovereign job-search CRM and operating system built on:
- **Backend**: FastAPI REST & Strawberry GraphQL API with CQRS pattern (read projections in GraphQL, governed command executions with cryptographic receipts via REST POST).
- **Core Domain**: SQLAlchemy ORM models, Alembic migrations, deterministic intent & skill scoring engine, candidate profile store, outbox messaging pipeline, Google Calendar slot sensing, Mosquitto MQTT & Gjallarhorn ASR integration, Obsidian note export.
- **Client SDK**: TypeScript SDK (`@ultradex/sdk`) with Zod contracts, typed GraphQL query documents, and command dispatchers.
- **Frontend**: SvelteKit 2 + Svelte 5 Glass UI (`ccc-glass`) with high-contrast design tokens, Command Home rail, full CRM pipeline views (Leads, Opportunities, Applications, Organizations, Contacts, Relationships, Inbox, Profile, Settings).
- **Runtime & Deployment**: Docker images (`ccc/ultradex:dev`, `ccc/glass:dev`), multi-service deployment to `k0s` on `vakr` (`10.10.20.101`) in namespace `ccc-tmp`, serving Glass UI on NodePort 30808 and API on NodePort 30800.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Candidate Profile Store & Taxonomy | Authoritative profile store (`/profile`), Nate Walker resume, 40+ CTO skills taxonomy (Expert/Advanced), production ML depth, target roles, comp bounds ($180k base / $250k target). | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Dynamic Job Sourcing Engine | `cli/sense_jobs.py` querying profile store to scrape and score postings from LinkedIn and 9 target career boards (Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS). | M1 | ORIGINAL_REQUEST §R1 |
| F3 | CRM Domain Models & Migrations | Database models and Alembic migrations for Organizations (`OrganizationDB`), Leads (`LeadDB`), Contacts (2,252 Dex contacts), Opportunities, Applications, Relationships. | M2 | ORIGINAL_REQUEST §R2 |
| F4 | Pipeline Lifecycle & Lead Conversion | Atomic Lead-to-Opportunity + initial Application creation state machine in `core/jobsearch_executors.py`, stage trackers, relationship sync. | M2 | ORIGINAL_REQUEST §R2 |
| F5 | Copilot Next Best Actions | Command Home (`/`) rail surfacing prioritized Next Best Actions derived from pipeline staleness, response SLAs, and interview milestones. | M3 | ORIGINAL_REQUEST §R3 |
| F6 | 3-Pill Recruiter Response Generator | 3-pill generator (*1. Accept & Share Availability*, *2. Request Scope & Comp Details*, *3. Polite Pass*) with live open slot injection. | M3 | ORIGINAL_REQUEST §R3 |
| F7 | Omnichannel In-App Messaging | In-app composer/dispatcher (`/inbox`, `/contacts/[id]`) sending via Gmail API (landing in Sent folder) and LinkedIn gateway. | M3 | ORIGINAL_REQUEST §R3 |
| F8 | Google Calendar Slot Sensing | Google Calendar sensing detecting scheduled rounds and computing open 30-min/45-min slots during working hours (09:00–17:00 CT). | M3 | ORIGINAL_REQUEST §R4 |
| F9 | Sovereign Voice & Interview Debriefs | Mosquitto MQTT (`ratatoskr:1883`) + Gjallarhorn ASR (`ratatoskr:18099`), structured debrief extraction (Summary, Questions, Action Items), Command Home action injection, Obsidian markdown export (`~/docs/40-personal/interviews/`). | M3 | ORIGINAL_REQUEST §R4 |
| F10 | GraphQL Read Projections | GraphQL types and queries for Profile, Leads, Organizations, Contacts, Messages, Next Best Actions, Calendar Events, and Interview Debriefs. | M4 | ORIGINAL_REQUEST §Acceptance |
| F11 | TypeScript SDK Extension | `@ultradex/sdk` Zod contracts, query documents, and client methods for all 8 new CRM/Copilot domains and command actions. | M4 | ORIGINAL_REQUEST §Acceptance |
| F12 | SvelteKit Glass UI Routes & Nav | Complete Glass UI route suite (`/`, `/inbox`, `/leads`, `/leads/[id]`, `/opportunities`, `/opportunities/[id]`, `/applications`, `/applications/[id]`, `/contacts`, `/contacts/[id]`, `/organizations`, `/organizations/[id]`, `/relationships`, `/profile`, `/settings`), LeftNav expansion, contrast compliance. | M5 | ORIGINAL_REQUEST §Acceptance |
| F13 | Pytest Test Suites | 100% pass across `test_jobsearch_executors.py`, `test_jobsearch_profile.py`, `test_jobsearch_copilot.py`, `test_jobsearch_messaging.py`, `test_jobsearch_calendar.py`, `test_jobsearch_gjallarhorn.py`. | M1-M3 | ORIGINAL_REQUEST §Acceptance |
| F14 | SDK & Frontend Test Suites | `npm test --workspace=@ultradex/sdk` and `npm test --workspace=ccc-glass` 100% pass with zero type errors. | M4-M5 | ORIGINAL_REQUEST §Acceptance |
| F15 | Container Builds & k0s Rollout | `ccc/ultradex:dev` and `ccc/glass:dev` build, import into k0s on `vakr` (`10.10.20.101`), rollout in `ccc-tmp`, live UI verified at `http://10.10.20.101:30808/`. | M6 | ORIGINAL_REQUEST §Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Candidate Profile & Sourcing Engine | `core/jobsearch_profile.py`, `cli/sense_jobs.py`, profile store seed, `tests/test_jobsearch_profile.py` | none | **DONE** (53 unit tests, 88 adversarial tests passing, CLEAN audit) |
| M2 | CRM Domain, Pipeline & Migrations | `core/jobsearch_models.py`, `migrations/versions/20260824_0004_crm_organizations_leads.py`, `core/jobsearch_executors.py`, lead conversion command, `tests/test_jobsearch_executors.py` | M1 | **DONE** (136 tests passing, migration verified) |
| M3 | Copilot, Messaging, Calendar & Voice | `core/jobsearch_copilot.py`, `core/jobsearch_messaging.py`, `core/jobsearch_calendar.py`, `core/jobsearch_gjallarhorn.py`, debrief extraction, Obsidian export, test suites | M1, M2 | **DONE** (46 new unit tests, 137 target tests passing) |
| M4 | GraphQL Projections & TypeScript SDK | `api/graphql/schema.py`, `api/graphql/jobsearch_types.py`, `sdk/typescript/src/*`, SDK tests | M1, M2, M3 | **DONE** (370 backend tests, 47 SDK vitests passing) |
| M5 | Glass SvelteKit Frontend Suite | `apps/web/src/routes/*`, `apps/web/src/lib/*`, `LeftNav.svelte`, unit/component tests | M4 | IN_PROGRESS |
| M6 | Container Builds, k0s Rollout & Live Verification | Docker images build, import into k0s on `vakr` (10.10.20.101), deploy to `ccc-tmp`, live endpoint verification at `http://10.10.20.101:30808/` | M5, TEST_READY | PLANNED |

## Interface Contracts
### Candidate Profile (`core/jobsearch_profile.py`) ↔ Scoring & Sourcing
- `CandidateProfileStore.get_profile()` -> `CandidateProfile` (skills: Dict[str, SkillTier], production_ml: Dict, target_roles: List[str], comp: CompExpectations).
- `sense_jobs.py` consumes `CandidateProfile` to query career boards and compute deterministic fit scores (0-100).

### CRM Models (`core/jobsearch_models.py`) ↔ State Machine (`core/jobsearch_executors.py`)
- `leads.convert` command takes `lead_id`, `stage`, `occurred_at`, `custom_title`, `contact_refs`, `next_action`, `next_action_deadline` and atomically creates active `OpportunityProjectionDB` and `ApplicationProjectionDB` in transaction with cryptographic receipt.

### Copilot (`core/jobsearch_copilot.py`) ↔ Messaging & Calendar
- `compute_next_best_actions(db, profile)` -> `List[NextBestAction]` (urgency, reason, action_type, target_entity).
- `generate_recruiter_replies(message, calendar_availability)` -> `Dict[str, RecruiterPillReply]` (pill 1: Accept & Share Slots, pill 2: Scope & Comp, pill 3: Polite Pass).

### Calendar & Voice (`core/jobsearch_calendar.py`, `core/jobsearch_gjallarhorn.py`)
- `get_open_working_hour_slots(start_date, end_date, duration_minutes=30)` -> `List[TimeSlot]` (09:00–17:00 CT).
- `extract_interview_debrief(transcript)` -> `InterviewDebrief` (executive_summary, questions_asked, action_items).
- `export_debrief_to_obsidian(debrief, vault_dir)` -> `Path`.

### GraphQL (`api/graphql/schema.py`) ↔ TypeScript SDK (`@ultradex/sdk`)
- GraphQL Queries: `profile`, `leads`, `lead`, `organizations`, `organization`, `contacts`, `contact`, `messages`, `nextBestActions`, `calendarEvents`, `availability`, `interviewDebriefs`, `interviewDebrief`.
- SDK Client methods matching each query and command dispatcher.

## Code Layout
- `api/`: FastAPI application, routers, GraphQL schema and resolvers.
- `core/`: SQLAlchemy models, migrations, domain services (profile, copilot, messaging, calendar, voice/ASR, executors, scoring).
- `cli/`: CLI runners (`sense_jobs.py`, `sense_dex.py`, `sense_gmail.py`, `mine_opportunities.py`).
- `sdk/typescript/`: TypeScript SDK (`@ultradex/sdk`) contracts, queries, commands, transport, and vitest suites.
- `apps/web/`: SvelteKit Glass web application (`ccc-glass`) routes, components, styling, and vitest suites.
- `deploy/k0s/`: Kubernetes / k0s deployment manifests for `vakr` (`10.10.20.101`) in namespace `ccc-tmp`.
- `tests/`: Pytest test suites covering backend execution, profile, copilot, messaging, calendar, voice, and GraphQL.
