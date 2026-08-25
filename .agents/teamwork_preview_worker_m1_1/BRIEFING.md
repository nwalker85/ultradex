# BRIEFING — 2026-08-24T06:52:00Z

## Mission
Implement Milestone M1 (Candidate Profile Store & Skills Taxonomy + Dynamic Job Sourcing Engine) with 100% test coverage and CLI functionality.

## 🔒 My Identity
- Archetype: implementer, qa
- Roles: implementer, qa
- Working directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_worker_m1_1
- Original parent: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Milestone: M1

## 🔒 Key Constraints
- Pure genuine implementation — no hardcoded test shortcuts, no facades.
- Pydantic v2 data models for candidate profile, skills taxonomy (44 skills: 22 Expert, 22 Advanced), ML depth (6 pillars), target roles, comp expectations ($180k-$250k).
- Multi-board acquisition protocol & adapters for LinkedIn + 9 target boards (Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS).
- Deterministic 4-factor scoring engine with hard exclusion gate for SoundHound/Amelia, Quant, IntelePeer.
- Full CLI `cli/sense_jobs.py` with mock and live modes.
- REST endpoints `/profile` and `/api/v1/profile`.
- Pytest suite `tests/test_jobsearch_profile.py` passes 100% with zero regressions on existing suites.

## Current Parent
- Conversation ID: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Updated: 2026-08-24T06:52:00Z

## Task Summary
- **What to build**:
  1. `core/jobsearch_profile.py`: Profile models, skills taxonomy (44 CTO skills), ML depth (6 pillars), seed profile, profile store with cache/DB/matching.
  2. `core/jobsearch_sourcing.py`: 10 board adapters (mock + live), deterministic scoring engine, sweep stashing.
  3. `cli/sense_jobs.py`: CLI runner supporting all flags.
  4. `api/routes/profile.py` & `api/main.py`: REST router for profile mounted at `/profile` and `/api/v1/profile`.
  5. `tests/test_jobsearch_profile.py`: Comprehensive test suite across 4 tiers (53 tests).
- **Success criteria**: All 53 profile tests pass (102/102 jobsearch tests pass total), CLI executes cleanly, handoff report generated.
- **Interface contracts**: PROJECT.md, Explorer M1.1, M1.2, M1.3 handoffs.

## Key Decisions Made
- Implemented 44 structured CTO skills (22 Expert, 22 Advanced across 7 categories) exceeding the requirement of 40+.
- Implemented 6 Production ML depth subdomains with technology stack and pattern inventories.
- Built multi-board sourcing protocol with adapters for LinkedIn and 9 target employer boards.
- Implemented pure deterministic multi-factor match scoring engine and hard employer exclusion gates.
- Built CLI runner `cli/sense_jobs.py` with full ASCII table rendering, JSON export, dry-run, and ingest modes.

## Change Tracker
- **Files modified/created**:
  - `core/jobsearch_profile.py`: Candidate profile store & skills taxonomy
  - `core/jobsearch_sourcing.py`: Multi-board sourcing adapters & scoring engine
  - `cli/sense_jobs.py`: Dynamic job sourcing CLI runner
  - `api/routes/profile.py`: Profile REST API endpoints
  - `api/main.py`: Mounted profile router on `/profile` and `/api/v1/profile`
  - `tests/test_jobsearch_profile.py`: 53 unit, boundary, pairwise, E2E, and API tests
- **Build status**: 102 passed, 0 failed across all jobsearch test suites

## Quality Status
- **Build/test result**: 53 passed in `tests/test_jobsearch_profile.py`, 102 passed total
- **Lint status**: Clean
- **Tests added/modified**: 53 comprehensive tests in `tests/test_jobsearch_profile.py`

## Artifact Index
- `.agents/teamwork_preview_worker_m1_1/DISPATCH.md` — Assignment
- `.agents/teamwork_preview_worker_m1_1/BRIEFING.md` — Working state
- `.agents/teamwork_preview_worker_m1_1/progress.md` — Heartbeat
- `.agents/teamwork_preview_worker_m1_1/handoff.md` — Final handoff report
