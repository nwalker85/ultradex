## 2026-08-24T13:25:08Z

<USER_REQUEST>
You are the M5 Worker implementing Milestone M5 (Glass SvelteKit Frontend Suite & Navigation).

Read the following before starting work:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Explorer M5.1 Handoff (UI Shell, LeftNav, Home, Profile, Settings): /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m5_1/handoff.md
- Explorer M5.2 Handoff (CRM Routes, Inbox, Vitest Architecture): /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m5_2/handoff.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_worker_m5_1
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. An auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE OF WORK & FILES TO IMPLEMENT:
1. `apps/web/src/lib/components/LeftNav.svelte`:
   - Complete 10-route sidebar (Pipeline, Network, Communications, System) with active state indicators and accessibility.
2. `apps/web/src/routes/+page.svelte`:
   - Command Home with Hero Pulse cards, Copilot Next Best Actions rail with priority badges and deep links, quick actions, and pipeline summary.
3. `apps/web/src/routes/profile/+page.svelte`:
   - Candidate Profile presenting Nate Walker's resume & bio, 44 CTO skills taxonomy (22 Expert, 22 Advanced across 7 categories), 6 Production ML depth pillars, target roles, and compensation bounds ($180k base / $250k target).
4. `apps/web/src/routes/leads/` (`+page.svelte`, `[id]/+page.svelte`):
   - Job leads table with source badges, fit score meter (0-100), match breakdown, risk tags, and one-click lead-to-opportunity conversion with `OperationTracker`.
5. `apps/web/src/routes/opportunities/` (`+page.svelte`, `[id]/+page.svelte`):
   - Opportunity pipeline table/board, pursuit scores, connected contacts, stage progression.
6. `apps/web/src/routes/applications/` (`+page.svelte`, `[id]/+page.svelte`):
   - Application lifecycle tracker, stage history timeline, next action alerts.
7. `apps/web/src/routes/organizations/` (`+page.svelte`, `[id]/+page.svelte`):
   - Employer directory with domain, size, industry, advocacy ratings, aggregated contacts and leads.
8. `apps/web/src/routes/contacts/` (`+page.svelte`, `[id]/+page.svelte`):
   - 2,252 Dex contacts directory with relationship tier, advocacy rating, search, communication history, and in-app message composer.
9. `apps/web/src/routes/relationships/+page.svelte`:
   - Sovereign relationship mapping table.
10. `apps/web/src/routes/inbox/+page.svelte`:
    - Omnichannel communication hub with message list, message detail viewer, 3-pill recruiter response generator (Accept & Availability with live GCal slots, Scope & Comp, Polite Pass), and in-app Gmail/LinkedIn message composer.
11. `apps/web/src/routes/settings/+page.svelte`:
    - Operator connection settings and 6-subsystem integration health matrix.
12. Pure helper modules and Vitest test suites in `apps/web/src/lib/`:
    - `leads.ts` & `leads.test.ts`
    - `organizations.ts` & `organizations.test.ts`
    - `contacts.ts` & `contacts.test.ts`
    - `applications.ts` & `applications.test.ts`
    - `inbox.ts` & `inbox.test.ts`
    - `relationships.ts` & `relationships.test.ts`
13. Verification:
    - Run: `npm test --workspace=ccc-glass`
    - Run: `npm run check --workspace=ccc-glass`
    - Run: `npm run build --workspace=ccc-glass`
</USER_REQUEST>
