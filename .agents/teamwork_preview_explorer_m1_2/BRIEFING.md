# BRIEFING — 2026-08-24T06:47:00Z

## Mission
Investigate and design `cli/sense_jobs.py` (Dynamic Job Sourcing Engine) across LinkedIn and 9 target career boards for Milestone M1.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, specification design
- Working directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_2
- Original parent: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Milestone: M1 (Dynamic Job Sourcing Engine)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Produce exact, production-ready specification and technical design for `cli/sense_jobs.py`
- Write handoff report to `.agents/teamwork_preview_explorer_m1_2/handoff.md`
- Communicate findings via `send_message` to parent

## Current Parent
- Conversation ID: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Updated: not yet

## Investigation State
- **Explored paths**: `PROJECT.md`, `ORIGINAL_REQUEST.md`, `cli/sense_dex.py`, `cli/sense_gmail.py`, `cli/mine_opportunities.py`, `core/jobsearch_sources.py`, `core/jobsearch_scoring.py`, `core/jobsearch_models.py`, `core/jobsearch_executors.py`, `.agents/teamwork_preview_explorer_m1_1/handoff.md`
- **Key findings**:
  - Existing Sense CLI runners (`sense_dex.py`, `sense_gmail.py`) use a 4-stage sweep/stash/declare/submit protocol.
  - Designed complete multi-board sourcing architecture for LinkedIn + 9 target career boards (Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS) with both live HTTP fetchers and deterministic offline mock generators.
  - Formulated 4-rule deterministic match scorer calculating Role match % (35%), Skill overlap % (40%), Compensation fit % (15%), and Location fit % (10%), backed by hard employer exclusion gates.
  - Designed structured data models (`RawJobPosting`, `MatchBreakdown`, `ScoredJobLead`, `JobSensingSummary`) and `JobSweep` declaration stash integration.
  - Specified complete CLI runner `cli/sense_jobs.py` (`--live`, `--mock`, `--board`, `--limit`, `--min-score`, `--dry-run`, `--json`, `--output`, `--ingest`) and async Python API `JobSourcingEngine`.
- **Unexplored areas**: None for M1.2.

## Key Decisions Made
- Sourcing engine adapters support both live ATS endpoints (Greenhouse, Lever, Ashby, SmartRecruiters, Amazon, Google) and high-fidelity deterministic mock fixtures for 100% test reliability.
- Scorer evaluates against both candidate profile's 44-skill taxonomy / ML depth and Intent singleton targeting / employer exclusions.
- Exclusion gate automatically identifies alias groupings (e.g. SoundHound AI / Amelia) to score 0 and flag `employer_excluded`.

## Artifact Index
- `.agents/teamwork_preview_explorer_m1_2/DISPATCH.md` — Inbound dispatches
- `.agents/teamwork_preview_explorer_m1_2/progress.md` — Liveness & task checklist
- `.agents/teamwork_preview_explorer_m1_2/BRIEFING.md` — Persistent state index
- `.agents/teamwork_preview_explorer_m1_2/handoff.md` — Final technical design specification
