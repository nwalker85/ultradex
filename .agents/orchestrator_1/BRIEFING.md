# BRIEFING — 2026-08-24T13:25:15Z

## Mission
Deliver full Career Command Center Job-Search CRM and Operating System across Backend/DB, GraphQL, TypeScript SDK, SvelteKit Glass UI, Copilot, Voice/Calendar integration, test suites, and k0s deployment.

## 🔒 My Identity
- Archetype: orchestrator
- Roles: [orchestrator, user_liaison, human_reporter, successor]
- Working directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/orchestrator_1
- Original parent: Sentinel
- Original parent conversation ID: a41f247b-2c52-4e4b-8762-b02cd9430ca9

## 🔒 My Workflow
- **Pattern**: Project Pattern (Dual Track: Implementation Track + E2E Testing Track)
- **Scope document**: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
1. **Decompose**:
   - M1: Candidate Profile & Sourcing Engine (`core/jobsearch_profile.py`, `cli/sense_jobs.py`, `tests/test_jobsearch_profile.py`) [DONE]
   - M2: CRM Domain, Pipeline & Migrations (`OrganizationDB`, `LeadDB`, lead conversion, `tests/test_jobsearch_executors.py`) [DONE - 136 tests passing]
   - M3: Copilot, Messaging, Calendar & Voice (`core/jobsearch_copilot.py`, `core/jobsearch_messaging.py`, `core/jobsearch_calendar.py`, `core/jobsearch_gjallarhorn.py`, test suites) [DONE - 137 target tests passing]
   - M4: GraphQL Projections & TypeScript SDK (`api/graphql/schema.py`, `@ultradex/sdk`) [DONE - 370 backend tests, 47 SDK vitests passing]
   - M5: Glass SvelteKit Frontend Suite (`apps/web/src/routes/*`, `apps/web/src/lib/*`, LeftNav, tests) [in-progress]
   - M6: Container Builds, k0s Rollout & Live Verification (`ccc/ultradex:dev`, `ccc/glass:dev`, k0s in `ccc-tmp`, `http://10.10.20.101:30808/`) [pending]
2. **Dispatch & Execute**:
   - Direct iteration loop per milestone: 2-3 Explorers -> 1 Worker -> 2 Reviewers -> 2 Challengers -> 1 Auditor -> Gate.
3. **On failure**:
   - Retry -> Replace -> Skip (Auditor non-skippable) -> Redistribute -> Redesign -> Escalate.
4. **Succession**: Threshold 16 spawns, write soft handoff, spawn successor.
- **Work items**:
  1. Phase 0: Survey [done]
  2. Phase 1: Architecture & Feature Inventory (`PROJECT.md`, `TEST_INFRA.md`) [done]
  3. Phase 2: Milestone M1 (Candidate Profile & Sourcing Engine) [done]
  4. Phase 3: Milestone M2 (CRM Domain, Pipeline & Migrations) [done]
  5. Phase 4: Milestone M3 (Copilot, Messaging, Calendar & Voice) [done]
  6. Phase 5: Milestone M4 (GraphQL & TypeScript SDK) [done]
  7. Phase 6: Milestone M5 (Glass SvelteKit Frontend) [in-progress]
  8. Phase 7: Milestone M6 & Final E2E Deployment Verification [pending]
- **Current phase**: 6 (Milestone M5)
- **Current focus**: Executing Milestone M5 Worker

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- NEVER investigate or explore the problem at the code level — dispatch Explorers for technical investigation.
- You MAY use file-editing tools ONLY for metadata/state files (.md) in your .agents/ folder.
- If a Forensic Auditor reports INTEGRITY VIOLATION, the milestone FAILS UNCONDITIONALLY.
- Never reuse a subagent after it has delivered its handoff — always spawn fresh.
- Never push directly to main/develop.
- Verify live running system before completion.

## Current Parent
- Conversation ID: a41f247b-2c52-4e4b-8762-b02cd9430ca9
- Updated: 2026-08-24T13:20:12Z

## Key Decisions Made
- Milestones M1-M4 verified and completed.
- M5 Worker dispatched to implement the complete Glass SvelteKit frontend route suite, LeftNav, and Vitest test suite.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|---|---|---|---|---|
| m5_explorer_1_fresh | teamwork_preview_explorer | UI Shell, LeftNav, Home, Profile Design | completed | bdc75572-372c-4343-9dfa-fc712a54af94 |
| m5_explorer_2_fresh | teamwork_preview_explorer | CRM Routes, Inbox & Vitest Design | completed | be0afca4-05e3-4d49-815d-0754020f607f |
| m5_worker_1 | teamwork_preview_worker | Glass SvelteKit Frontend Implementation | in-progress | abb52326-1bcf-44ad-a15d-3790bfb55341 |

## Succession Status
- Succession required: no
- Spawn count: 9 / 16 (Generation 2)
- Pending subagents: abb52326-1bcf-44ad-a15d-3790bfb55341
- Predecessor: none
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: task-309
- Safety timer: none

## Artifact Index
- /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md — Original User Request
- /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md — Global Project Specification & Feature Inventory
- /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/TEST_INFRA.md — E2E Test Strategy & Tier Matrix
- /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/orchestrator_1/progress.md — Progress & liveness tracker
- /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/orchestrator_1/GATE_STATUS.md — Gate verdict log
- /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/orchestrator_1/handoff.md — Generation 1 State Summary
