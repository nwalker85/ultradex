## 2026-08-24T08:30:09Z

You are Explorer M2.2 for Milestone M2 (Command Plane, Atomic Lead Conversion & State Machine).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m2_2
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce a complete technical specification for the Governed Command Plane and State Machine in `core/jobsearch_executors.py` and test plan for `tests/test_jobsearch_executors.py`.

TASKS:
1. Inspect `core/jobsearch_executors.py`, `core/jobsearch_commands.py`, `core/jobsearch_models.py`, and `tests/test_jobsearch_executors.py`.
2. Design handlers for new CRM commands:
   - `leads.create`: Creates a new unapplied `LeadDB` from sourcing or manual entry.
   - `leads.convert`: Atomic lead-to-opportunity conversion:
     * Validates lead is not already converted (refuses duplicate conversion fail-closed).
     * Updates `LeadDB(state='converted', converted_opportunity_id=opp_id)`.
     * Creates active `OpportunityProjectionDB`.
     * Creates initial `ApplicationProjectionDB`.
     * Syncs `RelationshipProjectionDB` if contact references provided.
     * Generates cryptographic accountability receipt.
   - `organizations.create` & `organizations.update`.
3. Design comprehensive test cases for `tests/test_jobsearch_executors.py` asserting all state transitions, atomic conversion properties, domain refusals, and receipt signatures.
4. Write your full design report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m2_2/handoff.md
5. Send a message to parent with your summary.
