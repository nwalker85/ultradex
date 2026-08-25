## 2026-08-24T09:10:52Z
You are Explorer M4.1 for Milestone M4 (GraphQL Read Projections & Resolvers).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m4_1
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce an exact, production-ready specification and technical design for GraphQL schema extensions in `api/graphql/schema.py` and `api/graphql/jobsearch_types.py`.

TASKS:
1. Inspect `api/graphql/schema.py`, `api/graphql/jobsearch_types.py`, and `core/jobsearch_projections.py`.
2. Design Strawberry GraphQL types and resolvers for:
   - `profile`: Candidate profile query (resume, 44 CTO skills, ML depth, target roles, comp).
   - `leads` and `lead(id)`: Unapplied job leads, fit scores, breakdown, risk flags.
   - `organizations` and `organization(id)`: Employer directory, advocacy score, firmographics.
   - `contacts` and `contact(id)`: Dex contacts with advocacy score and communication history.
   - `nextBestActions(limit)`: Copilot Next Best Actions for Command Home rail.
   - `generateRecruiterReplies(messageContext)`: 3-pill generator with injected calendar slots.
   - `availability(startDate, endDate, durationMinutes)` & `calendarEvents`: Google Calendar open slots (09:00–17:00 CT).
   - `messages(channel, status, threadId)`: Omnichannel outbox messages.
   - `interviewDebriefs(opportunityId)`: Sovereign voice debriefs.
3. Design pytest tests in `tests/test_graphql_jobsearch.py` or equivalent.
4. Write your full design report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m4_1/handoff.md
5. Send a message to parent upon completion.
