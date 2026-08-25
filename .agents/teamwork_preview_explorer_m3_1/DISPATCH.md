## 2026-08-24T09:01:10Z

You are Explorer M3.1 for Milestone M3 (Copilot Engine & Omnichannel In-App Messaging).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m3_1
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce an exact, production-ready specification and technical design for `core/jobsearch_copilot.py` and `core/jobsearch_messaging.py`.

TASKS:
1. Inspect existing code in `core/jobsearch_outreach.py`, `core/jobsearch_models.py`, `core/jobsearch_projections.py`, and `cli/sense_gmail.py`.
2. Design `core/jobsearch_copilot.py`:
   - Next Best Actions engine: evaluates pipeline opportunities, applications, unapplied high-fit leads, and unread communications to surface prioritized, actionable recommendations on the Command Home rail (`/`).
   - 3-Pill Recruiter Response Generator: takes incoming recruiter outreach and generates 3 contextual response pills:
     1. *Accept & Share Availability* (injects actual open time slots from calendar).
     2. *Request Scope & Comp Details* (asks for salary band, technical stack, reporting line).
     3. *Polite Pass* (declines gracefully while preserving network advocacy).
3. Design `core/jobsearch_messaging.py`:
   - In-app message composer and omnichannel dispatch engine.
   - Gmail API integration: draft and send emails, ensuring sent messages land in authentic Google `Sent` folder with proper thread headers (`In-Reply-To`, `References`).
   - LinkedIn messaging adapter support.
   - Outbox tracking and updating `ContactDB.communication_history`.
4. Design test plans for `tests/test_jobsearch_copilot.py` and `tests/test_jobsearch_messaging.py`.
5. Write your complete design report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m3_1/handoff.md
6. Send a message to parent upon completion.
