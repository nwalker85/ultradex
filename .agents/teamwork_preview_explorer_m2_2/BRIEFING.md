# BRIEFING — 2026-08-24T08:33:05Z

## Mission
Investigate and produce a complete technical specification for the Governed Command Plane and State Machine in `core/jobsearch_executors.py` and test plan for `tests/test_jobsearch_executors.py`.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m2_2
- Original parent: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Milestone: M2 (Command Plane, Atomic Lead Conversion & State Machine)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement in source code
- Produce structured 5-component handoff report
- Governed Command Plane & State Machine in `core/jobsearch_executors.py`
- Handlers for `leads.create`, `leads.convert`, `organizations.create`, `organizations.update`
- Full test plan for `tests/test_jobsearch_executors.py`
- Fail-closed atomic conversion and cryptographic accountability receipt validation

## Current Parent
- Conversation ID: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Updated: 2026-08-24T08:33:05Z

## Investigation State
- **Explored paths**:
  - `core/jobsearch_executors.py` (handler registry, state machine transitions, projection stamping, receipt issuance, fail-closed refusal handling)
  - `core/jobsearch_commands.py` (gateway routing, idempotency lock claiming, entity mapping)
  - `core/jobsearch_models.py` & `core/models.py` (projections, checkpoint tracking, audit tables)
  - `core/jobsearch_receipts.py` & `ravenhelm_contracts` (Ed25519 cryptographic receipts)
  - `tests/test_jobsearch_executors.py` (25 baseline tests passing)
- **Key findings**:
  - Designed complete handler specifications for `leads.create`, `leads.convert`, `organizations.create`, `organizations.update`.
  - Defined atomic transaction sequence for `leads.convert` ensuring `LeadDB(state='converted', converted_opportunity_id=opp_id)`, `OpportunityProjectionDB`, `ApplicationProjectionDB`, and `RelationshipProjectionDB` records are created and stamped atomically or rolled back completely on failure.
  - Specified fail-closed `DomainRefusal("lead_already_converted")` preventing duplicate conversion.
  - Designed 12 comprehensive unit and integration test specifications for `tests/test_jobsearch_executors.py`.
- **Unexplored areas**: None for M2.2 scope.

## Key Decisions Made
- `leads.convert` will lock the target `LeadDB` row with `_locked_row()` (`with_for_update()`) and atomically create active `OpportunityProjectionDB` and `ApplicationProjectionDB` records while syncing any specified `dex_contact_ref` relationships.
- Designed comprehensive test suite asserting atomic properties, domain refusals, idempotency replays, and cryptographic signature validations.

## Artifact Index
- DISPATCH.md — Dispatch history
- progress.md — Liveness & task progress
- handoff.md — Final 5-component handoff report
