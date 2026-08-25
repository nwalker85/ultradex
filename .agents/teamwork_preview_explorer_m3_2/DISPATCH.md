## 2026-08-24T09:01:10Z
<USER_REQUEST>
You are Explorer M3.2 for Milestone M3 (Google Calendar, Sovereign Voice/Gjallarhorn & Obsidian Exporter).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m3_2
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce an exact, production-ready specification and technical design for `core/jobsearch_calendar.py` and `core/jobsearch_gjallarhorn.py`.

TASKS:
1. Inspect existing code in `core/` for Google Calendar, MQTT, and Obsidian integration patterns.
2. Design `core/jobsearch_calendar.py`:
   - Google Calendar integration: event sensing, interview round detection.
   - Working hours slot calculation: finds open 30-min and 45-min slots between 09:00 and 17:00 CT (Monday–Friday), excluding existing busy events and buffer times.
   - Formats availability blocks for insertion into recruiter email drafts.
3. Design `core/jobsearch_gjallarhorn.py`:
   - Mosquitto MQTT client connecting to `ratatoskr:1883` and Gjallarhorn ASR on `ratatoskr:18099`.
   - Audio ingestion / live transcript processing.
   - Structured interview debrief extraction:
     * Executive Summary
     * Questions Asked & Answers Given
     * Technical / Culture Fit Assessment & Red Flags
     * Action Items (thank-you note, follow-up deliverables)
   - Integration with Copilot: auto-injects action items into Next Best Actions.
   - Obsidian Note Exporter: writes formatted markdown note to `~/docs/40-personal/interviews/YYYY-MM-DD_<company>_<role>_debrief.md`.
4. Design test plans for `tests/test_jobsearch_calendar.py` and `tests/test_jobsearch_gjallarhorn.py`.
5. Write your complete design report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m3_2/handoff.md
6. Send a message to parent upon completion.
</USER_REQUEST>
