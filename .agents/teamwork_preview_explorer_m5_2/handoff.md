# Milestone M5.2 Handoff Report: SvelteKit CRM Views, Inbox & Frontend Vitest Suite

## 1. Observation

Direct investigation of the repository, backend schemas, TypeScript SDK contracts, and SvelteKit web application yielded the following facts:

### Codebase and Architecture State
- **Web App**: `apps/web` is a SvelteKit 2.61.0 application using Svelte 5.55.0 runes (`$state`, `$derived`, `$props`, `$effect`), Vite 6.4.0, Vitest 3.2.6, `@ravenhelm/ui-svelte` 0.1.0, and `@ultradex/sdk` 0.1.0 (`apps/web/package.json`).
- **Layout & Routing**:
  - `apps/web/src/routes/+layout.ts` configures static SPA output: `export const prerender = true; export const ssr = false;`.
  - `apps/web/src/lib/client.ts` exports `createClient(config: GlassConfig)` wrapping `UltradexClient` with `BrowserFetchTransport`.
  - `apps/web/src/lib/governed-write.ts` and `apps/web/src/lib/operation-tracker.svelte.ts` provide two-tier governed command submission (`submitGoverned(...)`) with idempotency key generation and `OperationTracker` polling.
  - Existing routes: `+page.svelte` (Command Home), `opportunities/` (`+page.svelte`, `[id]/+page.svelte`), `applications/` (`+page.svelte`, `[id]/+page.svelte` - placeholder), `relationships/` (`+page.svelte` - partial), `outreach/`, `operations/`, `settings/`, `sources/`.
  - Missing routes to implement: `leads/` (`+page.svelte`, `[id]/+page.svelte`), `organizations/` (`+page.svelte`, `[id]/+page.svelte`), `contacts/` (`+page.svelte`, `[id]/+page.svelte`), `inbox/` (`+page.svelte`), `profile/` (`+page.svelte`), and deep overhaul of `applications/` and `relationships/`.
  - Navigation: `apps/web/src/lib/components/LeftNav.svelte` must be expanded to include all CRM links (`Command`, `Inbox`, `Leads`, `Opportunities`, `Applications`, `Organizations`, `Contacts`, `Relationships`, `Profile`, `Settings`).

### Backend Projections & SDK Capabilities
- **Leads**:
  - GraphQL queries: `leads(first, after, minFitScore, state, employer)`, `lead(id)`.
  - Governed command: `leads.convert` (`client.convertLead({ leadId, stage, occurredAt, customTitle, targetRoleFamily, contactRefs, nextAction, nextActionDeadline }, { idempotencyKey })`), which atomically marks lead as converted, creates `OpportunityProjectionDB`, creates initial `ApplicationProjectionDB`, and syncs `RelationshipProjectionDB`s, returning `{ lead_id, opportunity_id, application_id, status: "converted", relationships_synced }`.
- **Organizations**:
  - GraphQL queries: `organizations(first, after, sortBy)`, `organization(id)`.
  - Governed commands: `organizations.create`, `organizations.update`.
- **Contacts**:
  - GraphQL queries: `contacts(first, after, organizationId, minAdvocacyScore, relationshipTier, search)`, `contact(id)` covering 2,252 Dex contacts with CRM profile, advocacy score, and `communicationHistory`.
- **Copilot & Omnichannel Messaging**:
  - GraphQL queries: `nextBestActions(limit)`, `generateRecruiterReplies(message, messageContext, calendarAvailability)`, `availability(startDate, endDate, durationMinutes, bufferMinutes)`, `calendarEvents(startDate, endDate)`, `messages(first, after, channel, status, threadId, recipientId)`.
  - REST endpoints: `POST /api/v2/messages/send` (`client.sendMessage(...)`), `POST /api/v2/messages/draft` (`client.createDraft(...)`).
- **Tests**:
  - `npm test --workspace=ccc-glass` currently executes 8 test files (110 tests) with 100% success in 1.88s.

---

## 2. Logic Chain

From these observations, we establish the technical specification for all M5 SvelteKit views and Vitest test suites:

### 2.1 Routing & Navigation Architecture

```
apps/web/src/routes/
├── +layout.svelte               # Root layout with AppShell, LeftNav, TopBar
├── +page.svelte                 # Command Home rail with NextBestActions, Freshness, Needs Attention
├── inbox/
│   └── +page.svelte             # Omnichannel Hub, 3-Pill Recruiter Reply Generator & Live Composer
├── leads/
│   ├── +page.svelte             # Job Leads Table, Source Badges, Fit Score (0-100), Quick Convert
│   └── [id]/
│       ├── +page.svelte         # Lead Dossier, Match Breakdown, Risk Tags, Governed Convert Form
│       └── +page.ts             # prerender/ssr parameters
├── opportunities/
│   ├── +page.svelte             # Pipeline Table/Board, Scored/Unscored/Excluded Partitioning
│   └── [id]/
│       ├── +page.svelte         # Opportunity Dossier, Evidence Refs, Score/Sync/Apply Actions
│       └── +page.ts
├── applications/
│   ├── +page.svelte             # Application Lifecycle Table, Stage Filters, Deadline Alerts
│   └── [id]/
│       ├── +page.svelte         # Stage Timeline, Artifact Refs, Governed Stage Transition Form
│       └── +page.ts
├── organizations/
│   ├── +page.svelte             # Employer Directory, Advocacy Ratings, Create Org Modal
│   └── [id]/
│       ├── +page.svelte         # Employer Dossier, Aggregated Contacts & Leads, Edit Org Modal
│       └── +page.ts
├── contacts/
│   ├── +page.svelte             # 2,252 Dex Contacts Directory, Tier/Score Filters, Search
│   └── [id]/
│       ├── +page.svelte         # Contact Dossier, AI Strategy, Communication History, In-App Composer
│       └── +page.ts
├── relationships/
│   └── +page.svelte             # Sovereign Relationship Mapping Table (Contact -> Org -> Opp)
├── profile/
│   └── +page.svelte             # Candidate Profile Dossier (44 CTO skills taxonomy, ML depth, Comp)
├── operations/                  # Governed operations audit log
├── outreach/                    # Outreach draft & approval log
└── settings/                    # Operator connection & token settings
```

### 2.2 Route Technical Specifications

#### 1. Leads (`/leads` & `/leads/[id]`)
- **`/leads/+page.svelte`**:
  - **State**: `minFitScoreFilter` (all, 80+, 60+, 40+), `stateFilter` (`""`, `"discovered"`, `"unapplied"`, `"converted"`, `"dismissed"`), `searchQuery`, `leads: Lead[]`, `loading: boolean`, `error: unknown`.
  - **UI Elements**:
    - Filter row with `<Select>` for status, `<Select>` for fit score, and search input `<Field>`.
    - `<Table columns={["Employer / Title", "Source Board", "Fit Score", "Match / Risks", "Status", "Actions"]}>`.
    - Source Board Badges: `<Badge tone="neutral">{lead.sourceBoard}</Badge>`.
    - Fit Score Meter: `<span class="ccc-fit-meter">{Math.round(lead.fitScore)}/100</span>` with tone coding (>=80 `success`, >=60 `warning`, <60 `neutral`).
    - Risk tags: `<Badge tone="warning">{flag}</Badge>`.
    - Quick Action: "Convert to Opportunity" button opening inline conversion modal or converting directly.
    - True-zero vs Filtered-zero empty state handling via `$lib/leads.ts`.
- **`/leads/[id]/+page.svelte`**:
  - Fetches single lead via `client.getLead(leadId)`.
  - Panels:
    1. **Header & Meta**: Title, Employer, External ID, Source Board, Link to job posting.
    2. **Compensation & Role**: Salary range (`$salaryMin` - `$salaryMax` `salaryCurrency`), Remote type (`remote`, `hybrid`, `onsite`), Location.
    3. **Fit Score & Match Breakdown**: Visual circular/bar score, skills matched vs missing, domain alignment.
    4. **Job Description & Requirements**: Full description text and structured requirements checklist.
    5. **Conversion Panel**: If `convertedOpportunityId` is present, display link to `/opportunities/[convertedOpportunityId]`. Otherwise, display **Convert Lead to Opportunity Composer**:
       - Form inputs: `customTitle` (defaults to lead title), `stage` (`applied`, `screening`, `technical`, `target`), `contactRefs` (select connected contacts), `nextAction`, `nextActionDeadline`.
       - Governed submission calling `client.convertLead(...)`.
       - `OperationTracker` resolves execution receipt and displays link to the newly created Opportunity.

#### 2. Opportunities (`/opportunities` & `/opportunities/[id]`)
- **`/opportunities/+page.svelte`**:
  - Status filters: `discovered`, `qualified`, `watching`, `applied`, `interviewing`, `offer`, `closed`.
  - Ranked partitioning using `partitionOpportunitiesForList`: Scored (descending), Unscored, Excluded.
  - "New Opportunity" composer modal (`opportunities.create`).
- **`/opportunities/[id]/+page.svelte`**:
  - Details: Employer, Title, Status, Score, Risk Flags.
  - "Why this score" panel with full score explanation.
  - Evidence references panel with cryptographic commitment and redacted summary.
  - Connected Contacts panel (synced relationships) with `SyncRelationshipAction`.
  - Associated Applications panel with link to `/applications/[id]`.
  - Actions: `ScoreOpportunityAction` (`opportunities.score`), `SyncRelationshipAction` (`relationships.sync`), `CreateApplicationAction` (`applications.create`).

#### 3. Applications (`/applications` & `/applications/[id]`)
- **`/applications/+page.svelte`**:
  - **State**: `statusFilter` (`""`, `"draft"`, `"applied"`, `"screening"`, `"interviewing"`, `"offer"`, `"rejected"`, `"withdrawn"`), `applications: Application[]`.
  - **UI Elements**:
    - Filter row with `<Select>` for stage.
    - `<Table columns={["Employer / Opportunity", "Application ID", "Stage", "Next Action", "Deadline", "Artifacts"]}>`.
    - Next Action Deadline Alerts:
      - Overdue: `<Badge tone="danger">Overdue: {deadline}</Badge>`
      - Due Today: `<Badge tone="warning">Due today</Badge>`
      - Upcoming: `<Badge tone="neutral">Due in {days}d</Badge>`
- **`/applications/[id]/+page.svelte`**:
  - Header: Application ID, linked Opportunity (Employer + Title), Current Stage.
  - **Stage Progression Timeline (`StageTracker`)**:
    - Horizontal or vertical step timeline showing stages: `applied` -> `screening` -> `interviewing` -> `offer`.
    - Detailed `stageHistory` audit table (Status, Occurred At, Evidence Ref).
  - **Next Action & Deadlines**:
    - Current `nextAction` and `nextActionDeadline`.
  - **Artifacts**: List of document refs and submission receipts.
  - **Governed Stage Transition Form**:
    - Select new status (`screening`, `interviewing`, `offer`, `rejected`, `withdrawn`), pick occurredAt, submit via `client.submitApplicationTransition(...)` with `OperationTracker`.

#### 4. Organizations (`/organizations` & `/organizations/[id]`)
- **`/organizations/+page.svelte`**:
  - **State**: `organizations: Organization[]`, `sortBy` (`"name"` | `"id"`), `searchQuery`.
  - **UI Elements**:
    - Search input and sort controls.
    - `<Table columns={["Organization", "Domain", "Industry", "Size", "Advocacy Rating", "Actions"]}>`.
    - Advocacy Rating display (`{advocacyRating}%` or star meter).
    - "Add Organization" modal/composer calling `client.createOrganization({ name, domain, industry, size, advocacyRating, notes })`.
- **`/organizations/[id]/+page.svelte`**:
  - Header: Organization Name, Domain (external link), Industry, Size, Advocacy Rating.
  - Notes: Internal employer intelligence.
  - **Aggregated Contacts Panel**:
    - Loads contacts via `client.getContacts({ organizationId })`.
    - Displays contacts at this organization with job titles, relationship tier, advocacy scores, and direct message actions.
  - **Aggregated Job Leads Panel**:
    - Loads open leads via `client.getLeads({ employer: organization.name })`.
    - Lists active leads with fit scores and conversion actions.
  - **Associated Opportunities Panel**:
    - Lists active pipeline opportunities for this employer.
  - **Edit Organization Composer**:
    - Updates domain, industry, size, advocacy rating, and notes via `client.updateOrganization(...)`.

#### 5. Contacts (`/contacts` & `/contacts/[id]`)
- **`/contacts/+page.svelte`**:
  - **State**: `searchQuery`, `relationshipTierFilter`, `minAdvocacyScoreFilter`, `organizationFilter`, `contacts: Contact[]`, `loading: boolean`.
  - **Filters**:
    - Search bar (debounced text search over name, company, title, email).
    - Relationship Tier dropdown: `champion`, `advocate`, `peer`, `recruiter`, `lead`, `unknown`.
    - Min Advocacy Score dropdown: `>=80`, `>=60`, `>=40`, `All`.
    - Neglected contacts toggle (AI value >= 60 & days since contact >= 30).
  - **UI Table**:
    - Columns: `Name / Title`, `Company`, `Relationship Tier`, `Advocacy Score`, `AI Value`, `Last Contacted`, `Actions`.
    - Neglected indicator: `<Badge tone="warning">Neglected</Badge>`.
    - Quick actions: "Message" (opens composer), "View Dossier" (links to `/contacts/[id]`).
- **`/contacts/[id]/+page.svelte`**:
  - Header: Name, Job Title, Company (linked to `/organizations/[id]`), Relationship Tier badge, Advocacy Score badge.
  - Contact Details: Email (mailto & copy), Phone, LinkedIn URL.
  - **AI Strategy Panel**:
    - AI Value Score (0-100) & `aiReason`.
    - Recommended `outreachStrategy` & `suggestedTiming`.
    - Last contacted timestamp and neglected status.
    - `crmNotes` panel.
  - **Communication History Timeline**:
    - Chronological log of past messages (`timestamp`, `channel`, `direction`, `subject`, `summary`, `messageId`).
  - **In-App Message Composer**:
    - Channel selector: `Gmail` vs `LinkedIn`.
    - Subject input and Body textarea.
    - "Send Message" (`client.sendMessage(...)`) and "Save Draft" (`client.createDraft(...)`).

#### 6. Relationships (`/relationships/+page.svelte`)
- **Table / Split View**:
  - Columns: `Contact`, `Opportunity`, `Context / Relevance`, `Relevance Score`, `Freshness`.
  - Direct links to `/contacts/[id]` and `/opportunities/[id]`.
  - Freshness badge per row.

#### 7. Inbox (`/inbox/+page.svelte`)
- **Omnichannel Communication Hub**:
  - **Two-Pane Layout**:
    - **Left Pane (Message List)**:
      - Channel filter: `All`, `Gmail`, `LinkedIn`, `Dex`.
      - Status filter: `All`, `Draft`, `Pending Approval`, `Approved`, `Sent`, `Failed`.
      - Search bar.
      - Message card list showing Sender Name, Recruiter handle, Subject snippet, Channel icon, Timestamp, Status badge.
    - **Right Pane (Message Detail & Copilot Generator)**:
      - Message Header: From, Channel, Date, Subject, Thread ID.
      - Message Body: Formatted text / HTML view.
      - **3-Pill Recruiter Response Generator**:
        - Button: "Generate AI Replies" / Auto-generated upon message selection.
        - Calls `client.generateRecruiterReplies({ message: context, calendarAvailability })`.
        - Fetches live Google Calendar availability via `client.getAvailability({ startDate, endDate, durationMinutes: 30 })`.
        - Renders 3 interactive pills:
          1. **Accept & Share Availability**: Injects live 30-min/45-min open Central Time slots (e.g., "Tuesday, Aug 25: 10:00–10:30 AM CT, 2:00–2:45 PM CT").
          2. **Request Scope & Comp Details**: Inquires on reporting structure, team size, base salary ($180k+ base), and target total comp ($250k target).
          3. **Polite Pass**: Cordially declines out-of-scope roles while maintaining networking connection.
        - Clicking a pill automatically fills the In-App Message Composer.
      - **In-App Message Composer**:
        - Channel toggle (Gmail vs LinkedIn).
        - Recipient, Subject, Body text.
        - Google Calendar slot insertion tool.
        - Actions:
          - "Send Message" (`client.sendMessage(...)`).
          - "Save Draft" (`client.createDraft(...)`).
          - "Prepare Governed Outreach" (`client.submitOutreachPrepare(...)`).

---

### 2.3 Frontend Vitest Test Suite Architecture

We specify pure, DOM-free helper modules in `apps/web/src/lib/` alongside unit tests in `*.test.ts`:

1. **`apps/web/src/lib/leads.ts` & `apps/web/src/lib/leads.test.ts`**:
   - `LEAD_STATUS_FILTERS = ["discovered", "unapplied", "converted", "dismissed"] as const`.
   - `leadsEmptyState(filter: LeadStatusFilter): LeadsEmptyState` (true-zero vs filtered-zero).
   - `filterLeads(leads: readonly Lead[], criteria: LeadFilterCriteria): Lead[]`.
   - `formatFitScore(score: number | null): string`.
   - `buildLeadConvertParameters(lead: Lead, overrides: Partial<LeadConvertParameters>): LeadConvertParameters`.
   - Tests: 12 unit tests verifying filtering, score formatting, conversion payload generation, and empty state copy.

2. **`apps/web/src/lib/organizations.ts` & `apps/web/src/lib/organizations.test.ts`**:
   - `sortOrganizations(orgs: readonly Organization[], sortBy: "name" | "advocacy" | "size"): Organization[]`.
   - `filterOrganizations(orgs: readonly Organization[], search: string): Organization[]`.
   - `formatAdvocacyRating(rating: number | null): string`.
   - `organizationsEmptyState(search: string): OrganizationsEmptyState`.
   - Tests: 10 unit tests verifying alphabetical sort, rating sort, case-insensitive search, and empty states.

3. **`apps/web/src/lib/contacts.ts` & `apps/web/src/lib/contacts.test.ts`**:
   - `CONTACT_RELATIONSHIP_TIERS = ["champion", "advocate", "peer", "recruiter", "lead", "unknown"] as const`.
   - `isNeglectedContact(contact: Contact): boolean` (aiValue >= 60 && daysSinceContact >= 30).
   - `filterContacts(contacts: readonly Contact[], criteria: ContactFilterCriteria): Contact[]`.
   - `sortCommunicationHistoryDesc(history: readonly CommunicationEntry[]): CommunicationEntry[]`.
   - `relationshipTierTone(tier: string | null): "success" | "accent" | "warning" | "neutral"`.
   - Tests: 14 unit tests verifying neglected calculation, tier badge mapping, multi-field search, and chronological history sorting.

4. **`apps/web/src/lib/applications.ts` & `apps/web/src/lib/applications.test.ts`**:
   - `APPLICATION_STATUS_STEPS = ["applied", "screening", "interviewing", "offer", "closed"] as const`.
   - `classifyApplicationDeadline(deadline: string | null, now?: Date): DeadlineClassification` (`"overdue" | "due-today" | "upcoming" | "none"`).
   - `applicationsEmptyState(filter: ApplicationStatusFilter): ApplicationsEmptyState`.
   - `formatStageHistory(history: readonly ApplicationStage[]): FormattedStageStep[]`.
   - Tests: 12 unit tests verifying deadline classification (boundary conditions for today, yesterday, 3 days out), stage step formatting, and empty states.

5. **`apps/web/src/lib/inbox.ts` & `apps/web/src/lib/inbox.test.ts`**:
   - `formatAvailabilitySlotsForEmail(slots: readonly DailyAvailability[]): string`.
   - `applyRecruiterPillToComposer(pill: RecruiterPillReply, recipientEmail: string): ComposeMessageInput`.
   - `filterMessages(messages: readonly OutboxMessage[], criteria: MessageFilterCriteria): OutboxMessage[]`.
   - `messageChannelTone(channel: MessageChannel): "accent" | "warning" | "neutral"`.
   - Tests: 14 unit tests verifying availability slot email formatting in Central Time, pill template mapping, subject/body synthesis, and message filtering.

6. **`apps/web/src/lib/relationships.ts` & `apps/web/src/lib/relationships.test.ts`**:
   - `filterRelationships(relationships: readonly Relationship[], query: string): Relationship[]`.
   - `relationshipsEmptyState(hasFilter: boolean): RelationshipsEmptyState`.
   - Tests: 6 unit tests verifying search and empty states.

---

## 3. Caveats

1. **Static SPA Routing & Server Endpoints**: The web app builds with `@sveltejs/adapter-static` (`prerender: true, ssr: false`). Dynamic routes like `/leads/[id]`, `/organizations/[id]`, `/contacts/[id]`, `/applications/[id]`, `/opportunities/[id]` rely on client-side routing via `$app/state` (`page.params.id`). In static mode, `+page.ts` must export `export const prerender = false;` or rely on the root SPA shell.
2. **GraphQL Client Data Loading**: SvelteKit routes use `createClient(config)` in `onMount()` with independent `try/catch` blocks for resilient section loading. If the backend is running without authentication on the same origin, `SAME_ORIGIN_PROXY_SENTINEL` is used.
3. **Live Google Calendar Token**: If Google OAuth tokens are not configured in the backend environment, `client.getAvailability(...)` and `client.getCalendarEvents(...)` return empty arrays gracefully, allowing the 3-pill recruiter generator to use fallback availability templates without crashing.

---

## 4. Conclusion

- The technical specification and architecture for Milestone M5 provides complete, production-ready designs for all CRM routes (`/leads`, `/leads/[id]`, `/opportunities`, `/opportunities/[id]`, `/applications`, `/applications/[id]`, `/organizations`, `/organizations/[id]`, `/contacts`, `/contacts/[id]`, `/relationships`, `/inbox`, `/profile`, `/settings`), navigation (`LeftNav.svelte`), and helper modules with Vitest test suites.
- The design strictly adheres to the established governed-write pattern (`submitGoverned` with `OperationTracker`), high-contrast Glass design tokens (`tokens.css`), and pure helper separation for fast, deterministic testing.
- The implementer can directly execute M5 using the exact file structure, interfaces, component properties, and test assertions outlined above.

---

## 5. Verification Method

To verify the implementation of this design:
1. **Frontend Vitest Suite**:
   ```bash
   npm test --workspace=ccc-glass
   ```
   Must pass all existing and new test suites (`leads.test.ts`, `organizations.test.ts`, `contacts.test.ts`, `applications.test.ts`, `inbox.test.ts`, `relationships.test.ts`, `command-home.test.ts`, `opportunity-ranking.test.ts`, `governed-write.test.ts`, `errors.test.ts`, `operation-tracker.test.ts`, `client.test.ts`) with 100% success.
2. **Svelte Typecheck**:
   ```bash
   npm run check --workspace=ccc-glass
   ```
   Must pass with zero TypeScript / Svelte errors.
3. **Frontend Production Build**:
   ```bash
   npm run build --workspace=ccc-glass
   ```
   Must build static assets into `apps/web/build/` without prerender errors.
4. **Live Verification**:
   Inspect routes `/`, `/inbox`, `/leads`, `/leads/lead-1`, `/opportunities`, `/applications`, `/organizations`, `/contacts`, `/relationships`, `/profile`, `/settings` in browser on port 5175.
