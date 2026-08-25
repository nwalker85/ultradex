# BRIEFING — 2026-08-24T06:43:00Z

## Mission
Perform a comprehensive survey of the deployment infrastructure, Docker build configuration, k0s manifests for vakr (10.10.20.101) in ccc-tmp, seed data fixtures (Dex contacts, resume, skills), external service integrations/mocks, and end-to-end verification harness.

## 🔒 My Identity
- Archetype: explorer
- Roles: [explorer, investigator, analyst]
- Working directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_survey_3
- Original parent: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Milestone: initial_survey

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Report findings with exact file paths and line numbers
- Output comprehensive handoff.md in working directory
- Communicate via send_message to parent (cf2c8251-7c24-4996-a11e-ef889ad2750a)

## Current Parent
- Conversation ID: cf2c8251-7c24-4996-a11e-ef889ad2750a
- Updated: 2026-08-24T06:43:00Z

## Investigation State
- **Explored paths**:
  - `Dockerfile`, `apps/web/Dockerfile`, `apps/web/docker/nginx.conf`, `docker-compose.yml`
  - `deploy/k0s/ccc.yaml`, `scripts/apply-gmail-sense-secret.sh`, `scripts/create-gmail-oauth-1password.sh`
  - `core/dex_client.py`, `core/models.py`, `core/jobsearch_models.py`, `core/jobsearch_sources.py`, `core/jobsearch_worker.py`, `core/jobsearch_scoring.py`, `core/jobsearch_gmail.py`, `core/jobsearch_executors.py`
  - `cli/sense_dex.py`, `cli/sense_gmail.py`, `cli/mine_opportunities.py`
  - `tests/test_sources_dex_delta.py`, `tests/test_sources_gmail.py`, `tests/test_k0s_gmail_sense.py`, `tests/test_jobsearch_executors.py`, `tests/test_jobsearch_scoring.py`, `tests/test_jobsearch_intent.py`, `tests/conftest.py`
  - `sdk/typescript/package.json`, `apps/web/package.json`, `packages/ui-svelte/package.json`
- **Key findings**:
  1. Docker images (`ccc/ultradex:dev`, `ccc/glass:dev`) have working Dockerfiles, but need deployment scripts for k0s container import (`k0s ctr images import`).
  2. k0s manifest `deploy/k0s/ccc.yaml` is fully defined for namespace `ccc-tmp` with NodePort 30808 (glass) and 30800 (api), ConfigMap `glass-nginx`, Deployments (postgres, redis, nats, api, worker, jobsearch-worker, glass), and CronJobs (gmail-sense, dex-sense, opportunity-miner).
  3. Secret management: `gmail-sense` script exists; `ultradex` secret bootstrap script is missing.
  4. Seed data: Intent is seeded in `IntentProjectionDB`; 2,252 Dex contacts are fetched via `DexClient` but lack a static hermetic offline fixture; Candidate Profile store (Resume, 40+ skills taxonomy) is missing.
  5. External services: Mosquitto (`ratatoskr:1883`), Gjallarhorn (`ratatoskr:18099`), Google Calendar, LinkedIn, and dynamic job scraper (`cli/sense_jobs.py`) require integration/mock modules and test suites.
  6. E2E verification test suites specified in acceptance criteria (Profile, Copilot, Messaging, Calendar, Gjallarhorn) are missing.
- **Unexplored areas**: None remaining within survey scope.

## Key Decisions Made
- Cataloged exact line references across Docker, Kubernetes, database models, CLI tools, tests, and configuration.
- Structured comprehensive 5-component handoff report.

## Artifact Index
- `handoff.md` — Complete survey analysis
- `progress.md` — Liveness status
- `DISPATCH.md` — Initial directive
