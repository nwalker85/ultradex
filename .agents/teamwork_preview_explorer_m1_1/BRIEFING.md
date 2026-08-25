# BRIEFING — 2026-08-24T06:45:30Z

## Mission
Investigate and produce an exact, production-ready specification and technical design for `core/jobsearch_profile.py` and the `/profile` store.

## 🔒 My Identity
- Archetype: explorer
- Roles: explorer, synthesis
- Working directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_1
- Original parent: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Milestone: M1 (Candidate Profile & Skills Taxonomy Store)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Output design to handoff.md in own agent folder
- Do NOT modify codebase directly

## Current Parent
- Conversation ID: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `core/jobsearch_models.py` (projections, singleton intent pattern)
  - `core/jobsearch_scoring.py` (deterministic scoring rules, token overlap, employer exclusions)
  - `core/models.py` (database base, contacts, operations, settings)
  - `api/main.py` & `api/routes/` (FastAPI router mounts, dependencies, auth)
  - `tests/test_jobsearch_intent.py` & `tests/test_jobsearch_scoring.py` (intent fixtures, calibrated exclusions)
  - `PROJECT.md` & `.agents/ORIGINAL_REQUEST.md` (architecture, acceptance criteria)
- **Key findings**:
  - No authoritative candidate profile model or store exists yet (`core/jobsearch_profile.py` is absent).
  - Designed full Pydantic data architecture: `CandidateProfile`, `CandidateBio`, `WorkExperienceItem`, `EducationItem`, `SkillItem` (44 skills: 22 Expert, 22 Advanced), `ProductionMLDepth` (6 subdomains), `TargetRoleConfig`, `CompensationExpectations`.
  - Designed `CandidateProfileStore` with default ratified seed profile, thread-safe memory caching, database persistence (`profile_db` or JSON table), and skill text-matching utility.
  - Designed REST API router (`api/routes/profile.py` mounted at `/api/v1/profile` and `/profile`) supporting GET/PUT profile, skills taxonomy, ML depth, and target roles.
  - Designed comprehensive test suite for `tests/test_jobsearch_profile.py`.
- **Unexplored areas**: None for M1.1 scope.

## Key Decisions Made
- Profile data model uses Pydantic v2 (compatible with Ultradex FastAPI & strawberry GraphQL).
- Skills taxonomy structured into 7 distinct categories with 44 concrete skills: 22 Expert tier and 22 Advanced tier.
- Production ML depth taxonomy explicitly details 6 subdomains: LLM Orchestration, ASR/TTS & Voice, Fine-Tuning & Adaptation, Embeddings & RAG, Agent Loops & Tool Sandboxing, and Inference Hardware & Serving.
- Persistent store provides deterministic fallback to the ratified Nate Walker seed if no database row is present.

## Artifact Index
- DISPATCH.md — Incoming dispatch message
- BRIEFING.md — Agent persistent briefing
- progress.md — Liveness heartbeat
- handoff.md — 5-component technical design and specification report
