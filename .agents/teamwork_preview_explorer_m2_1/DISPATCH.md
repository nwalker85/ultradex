## 2026-08-24T08:30:09Z
You are Explorer M2.1 for Milestone M2 (CRM Database Models, Migrations & ORM Projections).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m2_1
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce a complete technical specification and design for CRM Database Models, Alembic Migrations, and ORM Projections.

TASKS:
1. Inspect `core/models.py`, `core/jobsearch_models.py`, `core/jobsearch_migrations.py`, and `migrations/versions/`.
2. Design database models and schemas for:
   - `OrganizationDB` (table `jobsearch_organizations`): id, name, domain, industry, size, advocacy_rating, notes, updated_at, created_at.
   - `LeadDB` (table `jobsearch_leads`): id, source_board, external_id, employer, organization_id, title, location, remote_type, salary_min, salary_max, salary_currency, url, description, requirements, fit_score, match_breakdown (JSONB), risk_flags (JSONB), state, converted_opportunity_id, created_at, updated_at.
   - Contact CRM extensions (advocacy score, CRM notes, communication history for the 2,252 Dex contacts).
3. Design Alembic migration script `migrations/versions/20260824_0004_crm_organizations_leads.py` ensuring clean upgrade and downgrade.
4. Write your full design report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m2_1/handoff.md
5. Send a message to parent with your summary.
