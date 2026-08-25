# Survey Explorer 2 Handoff Report: GraphQL API, TypeScript SDK, and SvelteKit Glass Frontend

## 1. Observation

A detailed survey of the codebase at `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req` was conducted across the GraphQL backend, TypeScript SDK (`@ultradex/sdk`), and SvelteKit Glass frontend (`ccc-glass`). Below are the direct observations with verbatim file paths, line numbers, and tool results.

### 1.1 GraphQL API & Schema (`api/graphql/`)

* **Schema Definition**: `api/graphql/schema.py` (lines 108–346).
  * The GraphQL schema uses Strawberry (`strawberry.Schema(query=Query)`, line 345).
  * **Query root (`Query`)** defines 13 fields (lines 113–343):
    * `opportunity(id: str) -> Opportunity | None` (lines 113–125)
    * `opportunities(first: int, after: str | None, status: str | None) -> OpportunityPage` (lines 127–143)
    * `application(id: str) -> Application | None` (lines 145–157)
    * `applications(first: int, after: str | None, status: str | None, opportunity_id: str | None) -> ApplicationPage` (lines 159–176)
    * `relationship(id: str) -> Relationship | None` (lines 179–191)
    * `relationships(first: int, after: str | None, opportunity_id: str | None) -> RelationshipPage` (lines 193–208)
    * `outreach_item(id: str) -> Outreach | None` (lines 211–223)
    * `outreach(first: int, after: str | None, status: str | None, opportunity_id: str | None) -> OutreachPage` (lines 225–240)
    * `approval(id: str) -> ApprovalEvidence | None` (lines 243–255)
    * `execution_receipt(operation_id: str) -> ExecutionReceiptEvidence | None` (lines 258–270)
    * `operation(id: str) -> Optional[OperationGQL]` (lines 273–280)
    * `operations(limit: int, status: Optional[str]) -> List[OperationGQL]` (lines 282–296)
    * `events(operation_id: str, first: int, after: Optional[int]) -> List[OperationEventGQL]` (lines 298–343)
  * **Mutation root**: Intentionally absent. `schema.mutation` is `None` (verified in `tests/test_graphql_jobsearch.py:742–743`). The system follows CQRS where queries read projections and commands are dispatched via governed REST POST endpoints (`/api/v2/job-search/commands/{command_name}` in `api/routes/v2/jobsearch_commands.py:31–104`).
* **GraphQL Types**: `api/graphql/jobsearch_types.py` (lines 1–376).
  * Defines Strawberry types: `EvidenceReference`, `ProjectionFreshness`, `ApplicationStage`, `Opportunity`, `Application`, `Relationship`, `Outreach`, `ApprovalEvidence`, `ExecutionReceiptEvidence`, and paginated wrappers `OpportunityPage`, `ApplicationPage`, `RelationshipPage`, `OutreachPage`.
* **Missing GraphQL Queries/Types for R1–R4**:
  * `Profile` (Candidate profile store, Nate Walker resume, 40+ CTO skills taxonomy, target roles, comp expectations): **0 queries / 0 types**.
  * `Lead` / `Leads` (Unapplied job postings with profile match breakdown): **0 queries / 0 types**.
  * `Organization` / `Organizations` (Employer directory aggregating contacts, leads, opps): **0 queries / 0 types**.
  * `Contact` / `Contacts` (2,252 Dex contacts with CRM profile, advocacy score, comm history): **0 queries / 0 types** (only string `dexContactRef` in `Relationship`).
  * `Message` / `Messages` / Inbound recruiter emails & 3-pill availability injection: **0 queries / 0 types**.
  * `NextBestAction` / `NextBestActions`: **0 queries / 0 types** (computed client-side in `command-home.ts` or missing backend resolver).
  * `CalendarEvent` / `CalendarEvents` / open slot sensing: **0 queries / 0 types**.
  * `InterviewDebrief` / `InterviewDebriefs` (Gjallarhorn meeting transcription / Obsidian export): **0 queries / 0 types**.
* **Router Mounting**: `api/main.py:155–159` mounts `GraphQLRouter(schema, context_getter=get_graphql_context)` at `/api/graphql`.
* **Backend GraphQL Tests**: `tests/test_graphql_jobsearch.py` (850 lines) and `tests/test_graphql_operations.py`.

---

### 1.2 TypeScript SDK (`@ultradex/sdk` in `sdk/typescript/`)

* **Package & Config**: `sdk/typescript/package.json` (lines 1–30).
  * Package: `@ultradex/sdk@0.1.0` (ESM module, node `>=20`).
  * Build: `tsc -p tsconfig.json`, Test: `vitest run`.
  * Dependencies: `zod@4.1.5`; DevDependencies: `typescript@5.9.3`, `vitest@3.2.6`.
* **Core SDK Structure**:
  * `sdk/typescript/src/index.ts`: Public module exports.
  * `sdk/typescript/src/contracts.ts` (768 lines): Zod schemas and TypeScript types for `Opportunity`, `Application`, `Relationship`, `Outreach`, `Operation`, `OperationLifecycleEvent`, `ApprovalEvidence`, `ExecutionReceiptEvidence`, and 9 command parameter schemas:
    `sources.ingest`, `opportunities.create`, `opportunities.score`, `applications.transition`, `relationships.sync`, `outreach.prepare`, `outreach.approve`, `outreach.send`, `evidence.export` (lines 106–116).
  * `sdk/typescript/src/jobsearch-queries.ts` (243 lines): GraphQL query document strings (`LIST_OPPORTUNITIES_QUERY`, `LIST_APPLICATIONS_QUERY`, `LIST_RELATIONSHIPS_QUERY`, `LIST_OUTREACH_QUERY`, `LIST_OPERATIONS_QUERY`, `GET_OPERATION_QUERY`, `GET_OPERATION_EVENTS_QUERY`, `GET_APPROVAL_QUERY`, `GET_EXECUTION_RECEIPT_QUERY`), input parsers (`opportunityVariables`, etc.), and Zod result schemas.
  * `sdk/typescript/src/jobsearch-commands.ts` (105 lines): `JobSearchCommandExecutor` submitting POST requests to `/api/v2/job-search/commands/{command_name}` with `Idempotency-Key`, `X-Correlation-Id`, and `X-Delegation-Id`.
  * `sdk/typescript/src/client.ts` (337 lines): `UltradexClient` implementing `UltradexReadClient` and `UltradexCommandClient`.
  * `sdk/typescript/src/transport.ts` (361 lines): Transport abstractions (`BrowserFetchTransport`, `UltradexTransport`), request executor (`UltradexRequestExecutor`), and error hierarchy (`UltradexHttpError`, `UltradexGraphQLError`, `UltradexSchemaError`, `UltradexAuthError`, `UltradexTimeoutError`, etc.).
* **Test Verification**:
  * Command: `npm test --workspace=@ultradex/sdk`
  * Result: **37 tests passed** across 3 test files:
    * `tests/client.test.ts`: 16 passed
    * `tests/commands.test.ts`: 12 passed
    * `tests/projections.test.ts`: 9 passed
* **Missing in `@ultradex/sdk`**:
  * No types, Zod schemas, queries, or command methods for:
    * Candidate Profile (`getProfile`, `updateProfile`)
    * Leads (`listLeads`, `getLead`, `convertLead`)
    * Organizations (`listOrganizations`, `getOrganization`)
    * Contacts (`listContacts`, `getContact`)
    * In-App Messages / Recruiter Responses (`listMessages`, `sendMessage`)
    * Next Best Actions (`listNextBestActions`)
    * Calendar Events & Open Slots (`listCalendarEvents`, `getAvailability`)
    * Interview Debriefs (`listInterviewDebriefs`, `getInterviewDebrief`)

---

### 1.3 SvelteKit Glass App (`ccc-glass` in `apps/web/`)

* **Package & Config**: `apps/web/package.json` (lines 1–28).
  * Package: `ccc-glass@0.1.0`.
  * Framework: SvelteKit 2 (`@sveltejs/kit@2.61.0`), Svelte 5 (`5.55.0`), Vite 6 (`6.4.0`), `@sveltejs/adapter-static@3.0.10`.
  * Dependencies: `@ravenhelm/ui-svelte@0.1.0`, `@ultradex/sdk@0.1.0`.
* **Routes Status Matrix**:
  | Route | File Path | Status / Implementation Lines |
  |---|---|---|
  | `/` (Command Home) | `apps/web/src/routes/+page.svelte` | **Implemented** (473 lines). Freshness strip over 4 projections, Needs Attention rail (4 categories), summary tables for Opportunities, Applications, Outreach, Operations. |
  | `/opportunities` | `apps/web/src/routes/opportunities/+page.svelte` | **Implemented** (229 lines). Status filter, ranked score partitioning (scored/unscored/excluded), CreateOpportunityComposer. |
  | `/opportunities/[id]` | `apps/web/src/routes/opportunities/[id]/+page.svelte` | **Implemented** (232 lines). Detail view, ScoreOpportunityAction, SyncRelationshipAction, evidence list. |
  | `/applications` | `apps/web/src/routes/applications/+page.svelte` | **Stubbed placeholder** (25 lines). EmptyState "No applications yet". |
  | `/applications/[id]` | `apps/web/src/routes/applications/[id]/+page.svelte` | **Stubbed placeholder** (29 lines). EmptyState "Application detail not yet built". |
  | `/relationships` | `apps/web/src/routes/relationships/+page.svelte` | **Partially implemented** (77 lines). Shows table (Contact, Opportunity, Context). Missing clean table layout (Name -> Organization -> Role -> Context) and 2,252 contact integration. |
  | `/outreach` | `apps/web/src/routes/outreach/+page.svelte` | **Stubbed placeholder** (26 lines). EmptyState "Outreach list not yet built". |
  | `/outreach/[id]` | `apps/web/src/routes/outreach/[id]/+page.svelte` | **Stubbed placeholder** (30 lines). EmptyState "Outreach detail not yet built". |
  | `/operations` | `apps/web/src/routes/operations/+page.svelte` | **Stubbed placeholder** (29 lines). EmptyState "Activity browser not yet built". |
  | `/operations/[id]` | `apps/web/src/routes/operations/[id]/+page.svelte` | **Stubbed placeholder** (29 lines). EmptyState "Operation detail not yet built". |
  | `/sources` | `apps/web/src/routes/sources/+page.svelte` | **Stubbed placeholder** (27 lines). EmptyState "Source ingest not yet built". |
  | `/settings` | `apps/web/src/routes/settings/+page.svelte` | **Implemented** (69 lines). API base URL, operator token, test connection. |
  | `/inbox` | *None* | **MISSING** — Required by R3. |
  | `/leads` | *None* | **MISSING** — Required by R2. |
  | `/leads/[id]` | *None* | **MISSING** — Required by R2. |
  | `/contacts` | *None* | **MISSING** — Required by R2 (2,252 Dex contacts). |
  | `/contacts/[id]` | *None* | **MISSING** — Required by R2. |
  | `/organizations` | *None* | **MISSING** — Required by R2. |
  | `/organizations/[id]` | *None* | **MISSING** — Required by R2. |
  | `/profile` | *None* | **MISSING** — Required by R1. |
* **Navigation Layout**: `apps/web/src/lib/components/LeftNav.svelte` (lines 23–195).
  * Items currently configured: Command (`/`), Opportunities (`/opportunities`), Applications (`/applications`), Relationships (`/relationships`), Outreach (`/outreach`), Operations (`/operations`), Settings (`/settings`).
  * Missing items: Profile (`/profile`), Leads (`/leads`), Organizations (`/organizations`), Contacts (`/contacts`), Inbox (`/inbox`).
* **Design Tokens & Accessibility/Contrast**:
  * Design tokens in `packages/ui-svelte/src/lib/tokens.css` (lines 8–130) provide dark and light themes (`--rh-color-background-canvas: #0e1014`, `--rh-color-surface-base: #12141a`, `--rh-color-text-primary: #e6eaf2`, `--rh-color-text-muted: #8690a5`, `--rh-color-accent-primary: #7fa3c8`).
  * Global accessibility enhancements in `apps/web/src/app.css` (lines 13–52) provide high-contrast hover colors (`#b8dcff`, `#cde6ff`), 3px underline offsets, and semantic `<th scope="row">` styling.
  * Nav items have `aria-current="page"`, `aria-label="Primary"`, and `aria-hidden="true"` on SVGs (`LeftNav.svelte:27, 40`).
* **Frontend Test Suite**:
  * Command: `npm test --workspace=ccc-glass`
  * Result: **110 tests passed** across 8 test suites:
    * `src/lib/opportunity-ranking.test.ts`: 18 passed
    * `src/lib/opportunities.test.ts`: 8 passed
    * `src/lib/whats-next.test.ts`: 1 passed
    * `src/lib/command-home.test.ts`: 27 passed
    * `src/lib/errors.test.ts`: 11 passed
    * `src/lib/client.test.ts`: 4 passed
    * `src/lib/governed-write.test.ts`: 34 passed
    * `src/lib/operation-tracker.test.ts`: 7 passed

---

## 2. Logic Chain

1. **Premise 1 (CQRS Architecture)**: The backend API implements strict CQRS where GraphQL (`api/graphql/schema.py`) serves read projections, while mutations execute asynchronously through governed REST endpoints (`/api/v2/job-search/commands/{command_name}`).
2. **Premise 2 (SDK Alignment)**: The TypeScript SDK (`@ultradex/sdk`) mirrors the GraphQL schema via strict Zod-validated read queries in `src/jobsearch-queries.ts` and command dispatchers in `src/jobsearch-commands.ts`.
3. **Premise 3 (Frontend Status)**: The SvelteKit Glass frontend (`apps/web`) currently implements Command Home (`/`), Opportunities (`/opportunities`, `/opportunities/[id]`), and Settings (`/settings`), while Applications and Operations are placeholders, and the remaining CRM and Copilot domains (Profile, Leads, Contacts, Organizations, Inbox) do not exist yet.
4. **Premise 4 (Requirements Delta)**:
   - *Requirement R1 (Candidate Profile)* requires `/profile` with Nate Walker's resume, 40+ CTO skills taxonomy, target roles, and comp expectations, plus `cli/sense_jobs.py`. Currently, `cli/sense_jobs.py` and `/profile` routes/APIs are missing.
   - *Requirement R2 (CRM Pipeline Lifecycle)* requires Contacts (`/contacts`, `/contacts/[id]`), Organizations (`/organizations`, `/organizations/[id]`), Leads (`/leads`, `/leads/[id]`), Opportunities (`/opportunities`, `/opportunities/[id]`), Applications (`/applications`, `/applications/[id]`), and Relationships (`/relationships`). Currently, Contacts, Organizations, and Leads are completely absent; Applications is stubbed; Relationships lacks the full CRM table.
   - *Requirement R3 (Copilot & Omnichannel Messaging)* requires Command Home Next Best Actions, 3-pill recruiter response generator, and `/inbox` with Gmail/LinkedIn dispatch. Currently, `/inbox` is missing and Next Best Actions needs integration with the 3-pill generator.
   - *Requirement R4 (Calendar & Sovereign Voice Engine)* requires Google Calendar sensing for open slots and Gjallarhorn ASR / Mosquitto MQTT meeting transcription. Currently, no GraphQL types or SDK queries exist for calendar events or interview debriefs.

---

## 3. Caveats

* **Alternative Query Fallbacks**: In `apps/web/src/routes/opportunities/[id]/+page.svelte:58–65`, single-entity lookup currently calls `listOpportunities({first: 100})` client-side because the SDK does not wrap the single `opportunity(id)` GraphQL query directly.
* **Backend Database Models**: The underlying database tables (`jobsearch_opportunities`, `jobsearch_applications`, `jobsearch_relationships`, `jobsearch_outreach`, `jobsearch_intent`) exist in `core/jobsearch_models.py`, but Contacts/Organizations/Leads tables and migrations require expansion to fulfill the 2,252 Dex contacts and employer directory specs.
* **No Code Modified**: This survey is strictly read-only; no code files were edited.

---

## 4. Conclusion

The existing codebase provides a solid, working CQRS foundation with 37 passing SDK tests and 110 passing frontend unit tests. However, there is a substantial scope gap between the existing foundation and the complete CRM & Copilot specification:

1. **GraphQL API (`api/graphql/`)**: Needs new GraphQL queries and types for `Profile`, `Leads`, `Organizations`, `Contacts`, `Messages`, `NextBestActions`, `CalendarEvents`, and `InterviewDebriefs`.
2. **TypeScript SDK (`@ultradex/sdk`)**: Needs Zod contracts, query documents, and client methods for all 8 missing domain entities and their associated command mutations.
3. **SvelteKit Glass App (`ccc-glass`)**:
   - Needs new routes: `/profile`, `/leads`, `/leads/[id]`, `/organizations`, `/organizations/[id]`, `/contacts`, `/contacts/[id]`, `/inbox`.
   - Needs implementation of stubbed routes: `/applications`, `/applications/[id]`, `/relationships` (upgraded table).
   - Needs updated `LeftNav.svelte` reflecting the complete CRM suite (Profile, Command, Leads, Opportunities, Applications, Organizations, Contacts, Relationships, Inbox, Settings).
   - Needs component and unit test suites covering the new routes.

---

## 5. Verification Method

To independently verify these findings:

1. **Run SDK test suite**:
   ```bash
   npm test --workspace=@ultradex/sdk
   ```
   *Expected*: 37 tests pass across `client.test.ts`, `commands.test.ts`, and `projections.test.ts`.

2. **Run SvelteKit Glass test suite**:
   ```bash
   npm test --workspace=ccc-glass
   ```
   *Expected*: 110 tests pass across 8 test files in `apps/web/src/lib/`.

3. **Inspect GraphQL schema**:
   ```bash
   python -c "from api.graphql.schema import schema; print(schema.query); print(schema.mutation)"
   ```
   *Expected*: Outputs Query type with 13 fields; Mutation is `None`.

4. **Verify route file inventory**:
   ```bash
   find apps/web/src/routes -name "+page.svelte"
   ```
   *Expected*: 10 routes found (`/`, `/opportunities`, `/opportunities/[id]`, `/applications`, `/applications/[id]`, `/relationships`, `/outreach`, `/outreach/[id]`, `/operations`, `/operations/[id]`, `/sources`, `/settings`). Note `/inbox`, `/leads`, `/contacts`, `/organizations`, and `/profile` are absent.
