# Dispatch for Milestone M1 Explorer 2: Dynamic Job Sourcing Engine (cli/sense_jobs.py)

- Milestone: M1 (Dynamic Job Sourcing Engine across LinkedIn & 9 Target Career Boards)
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_2
- Original Request: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- Project Scope: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md

## 2026-08-24T06:44:00Z
You are Explorer M1.2 for Milestone M1 (Dynamic Job Sourcing Engine).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_2
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce an exact, production-ready specification and technical design for `cli/sense_jobs.py` (Dynamic Job Sourcing Engine).

TASKS:
1. Inspect existing CLI tools `cli/sense_dex.py`, `cli/sense_gmail.py`, `cli/mine_opportunities.py`, and `core/jobsearch_sources.py`.
2. Design `cli/sense_jobs.py` and supporting sourcing engine:
   - Queries `CandidateProfileStore` / Intent for target roles, domains, and skills
   - Supports scraping / ingestion from LinkedIn and 9 target career boards: Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS.
   - Computes deterministic fit scores against candidate skills taxonomy and compensation bounds
   - Generates structured Job Posting / Lead records with full match breakdown (Role match %, Skill overlap %, Compensation fit)
   - Includes CLI runner options (--live, --mock, --limit, --board, --dry-run) and programmatic API.
3. Write your complete design and implementation specification to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_2/handoff.md

Do NOT write code to implementation files directly. When done, send a message to parent with your summary.
