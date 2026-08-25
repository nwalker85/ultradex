# E2E Test Infra: Career Command Center (CCC)

## Test Philosophy
- Opaque-box, requirement-driven testing covering backend services, GraphQL API, TypeScript SDK, SvelteKit Glass UI, and k0s deployment.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial + Real-World Workload Testing.

## Feature Inventory & Test Mapping
| # | Feature | Requirement Source | Tier 1 (Happy Path) | Tier 2 (Boundaries) | Tier 3 (Pairwise) | Tier 4 (E2E Scenario) |
|---|---------|-------------------|:-------------------:|:-------------------:|:-----------------:|:---------------------:|
| F1 | Candidate Profile & Skills Taxonomy | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ | ✓ |
| F2 | Dynamic Job Sourcing CLI | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ | ✓ |
| F3 | CRM Domain Models & Migrations | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ | ✓ |
| F4 | Pipeline Lifecycle & Lead Conversion | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ | ✓ |
| F5 | Copilot Next Best Actions | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| F6 | 3-Pill Recruiter Reply Generator | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| F7 | Omnichannel In-App Messaging | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| F8 | Google Calendar Slot Sensing | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |
| F9 | Sovereign Voice & Interview Debriefs | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |
| F10 | GraphQL Read Projections | ORIGINAL_REQUEST §Acceptance | ≥5 | ≥5 | ✓ | ✓ |
| F11 | TypeScript SDK Extension | ORIGINAL_REQUEST §Acceptance | ≥5 | ≥5 | ✓ | ✓ |
| F12 | SvelteKit Glass UI Routes | ORIGINAL_REQUEST §Acceptance | ≥5 | ≥5 | ✓ | ✓ |

## Test Architecture
- **Backend Test Runner**: `PYTHONPATH=. pytest tests/test_jobsearch_*.py`
- **SDK Test Runner**: `npm test --workspace=@ultradex/sdk`
- **Frontend Test Runner**: `npm test --workspace=ccc-glass`
- **Live Rollout Test Runner**: `curl -sS http://10.10.20.101:30808/` and `http://10.10.20.101:30800/health`

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Expected Outcome |
|---|----------|--------------------|------------------|
| S1 | Inbound Recruiter Email to Availability Reply | F1, F6, F7, F8, F10, F11 | Recruiter email parsed, 3-pill generator produces availability with real GCal 30-min slots in CT, sent via Gmail API into Sent folder. |
| S2 | Lead Ingestion to Opportunity & Application Conversion | F1, F2, F3, F4, F10, F11, F12 | Sourcing scrapes target board posting, scores fit against 40+ skills taxonomy, user converts lead, creating active opportunity & initial application in Glass UI. |
| S3 | Sovereign Interview Transcription to Obsidian Debrief | F5, F8, F9, F10, F12 | Interview recorded via Mosquitto MQTT & Gjallarhorn ASR, structured debrief extracted, action items injected into Command Home rail, Markdown note saved to Obsidian vault. |
| S4 | Full CRM Directory & Pipeline Exploration | F3, F10, F11, F12 | User navigates LeftNav across all 10+ Glass routes (`/contacts`, `/organizations`, `/leads`, `/opportunities`, `/applications`, `/profile`, `/inbox`), inspecting 2,252 Dex contacts with proper advocacy scores. |
| S5 | Complete k0s Cluster Deployment & Freshness Verification | F15 | Docker images build, import into k0s on `vakr` (10.10.20.101) in `ccc-tmp`, all pods reach Ready state, Glass UI renders without errors on NodePort 30808. |
