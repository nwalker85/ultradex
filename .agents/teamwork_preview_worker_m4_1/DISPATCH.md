## 2026-08-24T09:14:23Z
You are the M4 Worker implementing Milestone M4 (GraphQL Read Projections & TypeScript SDK Extension).

Read the following before starting work:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Explorer M4.1 Handoff (GraphQL Schema & Types): /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m4_1/handoff.md
- Explorer M4.2 Handoff (TypeScript SDK Extension): /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m4_2/handoff.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_worker_m4_1
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. An auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE OF WORK & FILES TO IMPLEMENT:
1. `api/graphql/jobsearch_types.py` & `api/graphql/schema.py`:
   - Implement Strawberry GraphQL types for Candidate Profile, Leads, Organizations, Contacts, Copilot Next Best Actions, Recruiter Response Pills, Calendar Availability, Outbox Messages, and Interview Debriefs.
   - Implement field resolvers on `Query` for all 9 domains: `profile`, `leads`, `lead`, `organizations`, `organization`, `contacts`, `contact`, `next_best_actions`, `generate_recruiter_replies`, `availability`, `calendar_events`, `messages`, `interview_debriefs`, `interview_debrief`.
2. `sdk/typescript/` (`@ultradex/sdk`):
   - Extend `src/contracts.ts` with Zod schemas and TypeScript types.
   - Extend `src/jobsearch-queries.ts` with typed GraphQL query documents and variable builders.
   - Extend `src/jobsearch-commands.ts` with command parameter mappers.
   - Extend `src/client.ts` with typed client methods.
   - Extend `src/index.ts` with barrel exports.
   - Add/update tests in `tests/` and run `npm test --workspace=@ultradex/sdk`.
3. Tests & Verification:
   - Run: `PYTHONPATH=. pytest tests/test_jobsearch_*.py`
   - Run: `npm test --workspace=@ultradex/sdk`

COMPLETION CRITERIA:
- All GraphQL types and queries execute cleanly.
- TypeScript SDK builds (`npm run build --workspace=@ultradex/sdk`) and all vitest tests pass 100%.
- Write your complete handoff report to:
  /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_worker_m4_1/handoff.md
- Send message to parent upon completion.
