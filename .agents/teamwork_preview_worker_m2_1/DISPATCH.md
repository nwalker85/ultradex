## 2026-08-24T08:34:29Z

You are the M2 Worker implementing Milestone M2 (CRM Database Models, Migrations, Pipeline Lifecycle & Atomic Lead Conversion).

Read the following before starting work:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Explorer M2.1 Handoff (DB Models & Migrations): /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m2_1/handoff.md
- Explorer M2.2 Handoff (Command Plane & Lead Conversion): /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m2_2/handoff.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_worker_m2_1
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. An auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE OF WORK & FILES TO IMPLEMENT:
1. `core/jobsearch_models.py`:
   - Implement `OrganizationDB` (table `jobsearch_organizations`) and `LeadDB` (table `jobsearch_leads`).
   - Update `JOBSEARCH_PROJECTION_TABLES` to include `jobsearch_organizations` and `jobsearch_leads`.
2. `core/models.py`:
   - Extend `ContactDB` with `advocacy_score`, `organization_id` FK, `crm_notes`, `communication_history` (JSON), `linkedin_url`, `relationship_tier`, and relationship to `OrganizationDB`.
3. `migrations/versions/20260824_0004_crm_organizations_leads.py`:
   - Create complete, bi-directional Alembic migration using `batch_alter_table` on `contacts`.
4. `core/jobsearch_executors.py` & `core/jobsearch_commands.py`:
   - Implement handlers for `leads.create`, `leads.convert` (atomic conversion to active Opportunity & initial Application, refusal on duplicate conversion), `organizations.create`, and `organizations.update`.
   - Update `_stamp_projection` mapping for `LeadDB` and `OrganizationDB`.
   - Support CRM commands in `JobSearchGatewayService`.
5. `core/jobsearch_projections.py`:
   - Implement read query functions `list_leads`, `get_lead`, `list_organizations`, `get_organization`.
6. `tests/test_jobsearch_executors.py` & `tests/test_jobsearch_migrations.py`:
   - Add tests verifying `leads.create`, `leads.convert` atomic creation and duplicate conversion refusals, `organizations.create/update`, and migration roundtrips.
   - Run verification: `PYTHONPATH=. pytest tests/test_jobsearch_executors.py tests/test_jobsearch_migrations.py tests/test_jobsearch_profile.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py`

COMPLETION CRITERIA:
- All new models, migrations, handlers, and projections implemented cleanly.
- All test suites pass 100% with zero regressions.
- Write your complete handoff report to:
  /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_worker_m2_1/handoff.md
- Send message to parent upon completion.
