## 2026-08-24T06:37:53Z

You are Survey Explorer 3 (Docker, k0s Deployment, Environment & Verification Infra).

Read the original request at: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
Your working directory is: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_survey_3
Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Perform a comprehensive survey of the deployment infrastructure, Docker build configuration, k0s manifests for vakr (10.10.20.101) in ccc-tmp, seed data (2,252 Dex contacts, resume, skills), external service integrations/mocks, and end-to-end verification harness.

TASKS:
1. Read ORIGINAL_REQUEST.md completely.
2. Explore Dockerfiles for backend (ccc/ultradex:dev) and frontend (ccc/glass:dev), container build scripts, docker-compose files.
3. Explore Kubernetes / k0s manifests for deploying to namespace `ccc-tmp` on `vakr` (`10.10.20.101`), NodePort 30808 or Ingress mapping.
4. Explore seed data fixtures (Dex contacts, resume, taxonomy, sample opportunities/leads).
5. Explore network / connection settings for Mosquitto MQTT (ratatoskr:1883), Gjallarhorn ASR (ratatoskr:18099), Google Calendar, Gmail, LinkedIn.
6. Document deployment readiness, missing manifests/scripts, seed data status, and end-to-end test requirements.
7. Write your complete, structured survey report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_survey_3/handoff.md

Do NOT write code or edit implementation files. Report findings with exact file paths and line numbers. When done, send a message to parent with summary and confirm handoff.md is written.
