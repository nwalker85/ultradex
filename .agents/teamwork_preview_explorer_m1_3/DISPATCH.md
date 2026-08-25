## 2026-08-24T06:43:46Z
You are Explorer M1.3 for Milestone M1 (Test Suite Architecture for tests/test_jobsearch_profile.py).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- TEST_INFRA.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/TEST_INFRA.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_3
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Design the complete, comprehensive pytest test suite for `tests/test_jobsearch_profile.py` verifying R1 acceptance criteria.

TASKS:
1. Inspect `tests/conftest.py`, `tests/test_jobsearch_intent.py`, and `tests/test_jobsearch_scoring.py` for testing patterns and fixtures.
2. Design test cases across Tiers 1-4 for `tests/test_jobsearch_profile.py`:
   - Profile Store & Taxonomy (resume text, 40+ skills Expert/Advanced tier partitioning, ML depth, comp expectations $180k-$250k)
   - Dynamic Job Sourcing (`cli/sense_jobs.py` on LinkedIn & all 9 target career boards: Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS)
   - Profile Match & Scoring Engine (exact scoring match breakdown, skill overlap calculation, compensation filtering)
   - Boundary & Negative Cases (unknown board, empty skills, out-of-range salary, special characters)
   - CLI execution and JSON output formatting.
3. Write your complete test plan and assertion specification to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_3/handoff.md

Do NOT write code to implementation files directly. When done, send a message to parent with your summary.
