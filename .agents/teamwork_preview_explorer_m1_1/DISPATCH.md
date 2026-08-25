## 2026-08-24T06:43:46Z

You are Explorer M1.1 for Milestone M1 (Candidate Profile & Skills Taxonomy Store).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_1
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce an exact, production-ready specification and technical design for `core/jobsearch_profile.py` and the `/profile` store.

TASKS:
1. Read existing code in `core/jobsearch_models.py`, `core/jobsearch_scoring.py`, `core/models.py`.
2. Design the candidate profile data structures and persistent store in `core/jobsearch_profile.py`:
   - Nate Walker's comprehensive resume & bio
   - 40+ CTO skills taxonomy structured into Expert (≥20 skills) and Advanced (≥20 skills) tiers covering AI/ML, Distributed Systems, Cloud/Infra, Frontend/Fullstack, Leadership, etc.
   - Production ML depth taxonomy (LLM orchestration, ASR/TTS, fine-tuning, embeddings/RAG, agent loops)
   - Target roles (CTO, VP of Engineering, Head of AI, Principal AI Architect, Technical Founder)
   - Compensation expectations ($180k base minimum, $250k target total comp)
   - REST endpoint router `/api/v1/profile` or `/profile` and profile retrieval / update methods.
3. Write your complete design and implementation specification to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m1_1/handoff.md

Do NOT write code to implementation files directly. When done, send a message to parent with your summary.
