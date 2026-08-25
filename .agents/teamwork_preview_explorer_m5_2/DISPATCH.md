## 2026-08-24T13:20:16Z
You are Explorer M5.2 for Milestone M5 (SvelteKit CRM Views, Inbox & Frontend Vitest Suite).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m5_2
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce an exact, production-ready specification and technical design for SvelteKit CRM Views (`/leads`, `/leads/[id]`, `/opportunities`, `/opportunities/[id]`, `/applications`, `/applications/[id]`, `/organizations`, `/organizations/[id]`, `/contacts`, `/contacts/[id]`, `/relationships`, `/inbox`) and the frontend Vitest test suite.

TASKS:
1. Inspect `apps/web/src/routes/` and existing page components.
2. Design routes:
   - `/leads` & `/leads/[id]`: Job lead table with source board badges, fit scores (0-100), match breakdown, risk tags, and one-click "Convert to Opportunity" action.
   - `/opportunities` & `/opportunities/[id]`: Opportunity pipeline board/table with stage trackers, connected contacts, and details.
   - `/applications` & `/applications/[id]`: Application lifecycle timeline, stage history, and next action items with deadline alerts.
   - `/organizations` & `/organizations/[id]`: Employer directory with advocacy score, domain, size, and aggregated contacts/leads.
   - `/contacts` & `/contacts/[id]`: 2,252 Dex contacts directory with advocacy score, relationship tier, search, and detail dossier with communication history and in-app message composer.
   - `/relationships`: Sovereign relationship mapping table.
   - `/inbox`: Omnichannel communication hub with message list, message detail viewer, 3-pill recruiter response generator (Accept & Availability with live GCal slots, Scope & Comp, Polite Pass), and Gmail/LinkedIn message composer.
3. Design Vitest test architecture in `apps/web/tests/` or `apps/web/src/`.
4. Write your full design report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m5_2/handoff.md
5. Send a message to parent upon completion.
