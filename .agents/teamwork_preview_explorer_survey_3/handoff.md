# Survey Explorer 3 Handoff Report: Docker, k0s Deployment, Seed Data, External Services & Verification Infra

## 1. Observation

A comprehensive survey was performed across the deployment infrastructure, container builds, k0s Kubernetes manifests, seed data fixtures, external integrations, and verification harness at `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req`.

---

### 1.1 Docker Build Infrastructure

* **Backend Dockerfile (`Dockerfile`)**:
  * Location: `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/Dockerfile` (lines 1–24).
  * Base Image: `python:3.11-slim` (line 1).
  * System Packages: `gcc`, `postgresql-client` (lines 6–9).
  * Package Resolution: Line 13 mounts secret `forgejo_netrc` (`--mount=type=secret,id=forgejo_netrc,target=/root/.netrc,required=false`) and points `--extra-index-url` to `http://hrafngud.ravenmask.net:3300/api/packages/nate/pypi/simple/` for `ravenhelm-contracts==0.5.0`.
  * Dependencies: `requirements.txt` includes FastAPI, Strawberry GraphQL, SQLAlchemy, Pydantic, Anthropic, arq, redis, psycopg2, cryptography, and nats-py.
  * Entrypoint / Default CMD: `CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port 8000"]` (line 23).
  * Image Tag: `ccc/ultradex:dev`.
  * Usage: Serves `api`, `worker` (`python -m arq core.workers.WorkerSettings`), `jobsearch-worker` (`python -m core.jobsearch_worker`), and CronJobs (`cli.sense_gmail`, `cli.sense_dex`, `cli.mine_opportunities`).
  * Missing Dependencies in `requirements.txt` for R4 Voice/MQTT: `paho-mqtt` / `aiomqtt` (or standard WebSocket/MQTT clients) for `ratatoskr:1883` and Gjallarhorn ASR integration.

* **Frontend Glass Dockerfile (`apps/web/Dockerfile`)**:
  * Location: `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/apps/web/Dockerfile` (lines 1–17).
  * Stage 1 (Build): `node:22-alpine AS build` (lines 1–10).
    * Copies `package.json`, `sdk/typescript`, `packages/ui-svelte`, `apps/web`.
    * Runs `npm install --workspace=ccc-glass --workspace=@ultradex/sdk --workspace=@ravenhelm/ui-svelte` (line 8).
    * Runs `npm run build --workspace=@ultradex/sdk` (line 9).
    * Runs `npm run build --workspace=ccc-glass` (line 10).
  * Stage 2 (Runtime): `nginx:1.27-alpine` (lines 12–16).
    * Copies `apps/web/docker/nginx.conf` to `/etc/nginx/conf.d/default.conf`.
    * Copies `/app/apps/web/build` to `/usr/share/nginx/html`.
    * Exposes port `8080` (line 15).
    * Healthcheck: `wget -qO- http://127.0.0.1:8080/ || exit 1` (line 16).
  * Image Tag: `ccc/glass:dev`.

* **Local Docker Compose (`docker-compose.yml`)**:
  * Location: `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/docker-compose.yml` (lines 1–137).
  * Services defined: `postgres` (port 5432), `redis` (port 6379), `nats` (ports 4222, 8222 with JetStream enabled), `api` (port 8000), `worker` (arq), `jobsearch-worker` (pull consumer).
  * Note: `ccc-glass` frontend is not defined in `docker-compose.yml` (only runs via `npm run dev --workspace=ccc-glass` or k0s).

---

### 1.2 Kubernetes / k0s Deployment Infrastructure (`deploy/k0s/ccc.yaml`)

* **Target Environment**:
  * Node/Host: `vakr` (`10.10.20.101`).
  * Kubeconfig: `$HOME/.kube/vakr-k0s.yaml` or SSH to `vakr-svc` (per `scripts/apply-gmail-sense-secret.sh:13, 33`).
  * Namespace: `ccc-tmp`.

* **Manifest Inventory (`deploy/k0s/ccc.yaml`, 410 lines)**:
  1. `ConfigMap` `glass-nginx` (lines 1–30):
     * Mounts into Nginx at `/etc/nginx/templates/default.conf.template`.
     * Proxies `/api/` -> `http://api:8000/api/` with `Authorization: "Bearer ${ULTRADEX_API_TOKEN}"`.
     * Proxies `/health` and `/health/ready` -> `http://api:8000/health`.
     * Serves static HTML/JS for Svelte SPA.
  2. `Service` definitions:
     * `postgres` (port 5432, ClusterIP, lines 32–42)
     * `redis` (port 6379, ClusterIP, lines 44–53)
     * `nats` (client 4222, monitor 8222, ClusterIP, lines 55–67)
     * `api` (port 8000 -> **NodePort 30800**, lines 69–80)
     * `glass` (port 8080 -> **NodePort 30808**, lines 82–93)
  3. `Deployment` definitions:
     * `postgres`: image `postgres:16-alpine`, user `ultradex`, password `ultradex_dev_password`, db `ultradex` (lines 94–123). Note: Uses ephemeral container storage.
     * `redis`: image `redis:7-alpine` (lines 124–146).
     * `nats`: image `nats:2.11-alpine` with `-js -m 8222 --store_dir /data` and emptyDir volume (lines 147–174).
     * `api`: image `ccc/ultradex:dev`, `imagePullPolicy: Never`, command `alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000`, envFrom secret `ultradex` (lines 175–215).
     * `worker`: image `ccc/ultradex:dev`, `imagePullPolicy: Never`, command `python -m arq core.workers.WorkerSettings`, envFrom secret `ultradex` (lines 216–245).
     * `jobsearch-worker`: image `ccc/ultradex:dev`, `imagePullPolicy: Never`, command `python -m core.jobsearch_worker`, envFrom secret `ultradex` (lines 246–275).
     * `glass`: image `ccc/glass:dev`, `imagePullPolicy: Never`, env `ULTRADEX_API_TOKEN` from secret `ultradex`, volumeMount from ConfigMap `glass-nginx` (lines 276–314).
  4. `CronJob` definitions:
     * `gmail-sense`: schedule `"17 */4 * * *"`, runs `python -m cli.sense_gmail` (lines 315–346).
     * `dex-sense`: schedule `"47 */4 * * *"`, runs `python -m cli.sense_dex` (lines 347–378).
     * `opportunity-miner`: schedule `"5 */2 * * *"`, runs `python -m cli.mine_opportunities` (lines 379–410).

* **Container Image Import Mechanism**:
  * Because `imagePullPolicy: Never` is set, images must be imported into k0s containerd directly on `vakr`:
    ```bash
    docker save ccc/ultradex:dev | ssh vakr-svc "sudo k0s ctr images import -"
    docker save ccc/glass:dev | ssh vakr-svc "sudo k0s ctr images import -"
    ```

* **Secrets Management Status**:
  * `gmail-sense` secret: Supported by script `scripts/apply-gmail-sense-secret.sh` (injects `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` from 1Password `Gmail OAuth - CCC Sense` into k0s namespace `ccc-tmp`).
  * `ultradex` secret: Needs `ULTRADEX_API_TOKEN`, `ULTRADEX_OPERATOR_ID`, `DEX_API_KEY`, `CLAUDE_API_KEY`, `ULTRADEX_ACCOUNTABILITY_HMAC_KEY`, `ULTRADEX_RECEIPT_ED25519_PRIVATE_KEY`, `ULTRADEX_RECEIPT_KEY_ID`, `ULTRADEX_EXECUTOR_PAIRWISE_ID`. No dedicated bootstrap script currently exists for applying this secret to `ccc-tmp`.

---

### 1.3 Seed Data & Fixtures Status

* **2,252 Dex Contacts**:
  * Live Sync: `core/dex_client.py` and `cli/sense_dex.py` connect to `https://api.prod.getdex.com/v1` with pagination over `data.nextCursor`.
  * Database Table: `ContactDB` (table `contacts` in `core/models.py:162–185`).
  * Delta & Storage: `compute_dex_delta` in `core/jobsearch_sources.py:48–83` tracks new, changed, and neglected contacts.
  * Status: Live sync works against the live Dex account (~2,252 contacts), but there is **no offline static JSON fixture** (e.g. `tests/fixtures/dex_contacts.json`) for hermetic offline testing.

* **Candidate Profile, Resume & Skills Taxonomy (Requirement R1)**:
  * Database Model: `IntentProjectionDB` in `core/jobsearch_models.py:136–164` holds targeting parameters (`target_role_families`, `target_domains`, `seniority_band`, `location_preference`, `remote_preference`, `employer_exclusions`, `weights`).
  * Baseline Seed: `cli/mine_opportunities.py:36–66` defines `DEFAULT_INTENT` and `tests/test_jobsearch_intent.py:47–98` defines `_ratified_intent_parameters()`.
  * Gap: Candidate Profile store (`/profile`), 40+ CTO skills taxonomy (Expert/Advanced), production ML depth, resume markdown/structured experience, and comp expectations ($180k base / $250k target) are not yet encapsulated in a dedicated Profile entity/store or GraphQL API.

* **Opportunities, Leads & Organizations Seed Data (Requirement R2)**:
  * Opportunities: `cli/mine_opportunities.py:213–305` extracts top 20 employer clusters from Dex contacts and 5 sample recruiter leads from Gmail (`Anthropic`, `Scale AI`, `OpenAI`, `LivePerson`, `Parloa`).
  * Leads & Organizations: Not yet represented as standalone seed files or database tables (currently mapped dynamically from Dex companies and Gmail threads).

---

### 1.4 External Services & Integration Settings (Requirement R3 & R4)

| External Service | Target Address / Config | Auth Mechanism | Current Implementation State |
|---|---|---|---|
| **Mosquitto MQTT** | `ratatoskr:1883` | TCP / Anonymous / User | **Missing** — No MQTT connection, topic subscriber/publisher, or stream listener implemented. |
| **Gjallarhorn ASR** | `ratatoskr:18099` | HTTP / WebSocket | **Missing** — No ASR audio client, structured debrief extractor (Exec Summary, Questions, Action Items), or Obsidian notes exporter (`~/docs/40-personal/interviews/`) implemented. |
| **Google Calendar** | Google Calendar API | OAuth 2.0 / Service Account | **Missing** — No interview round sensing or 30-min/45-min open slot availability calculator (09:00–17:00 CT) implemented. |
| **Gmail API** | `gmail.googleapis.com` | OAuth 2.0 (`gmail.readonly`) | **Partially implemented** — Sensing/sweeps (`core/jobsearch_gmail.py`, `cli/sense_gmail.py`) implemented; outbound sending from in-app composer (`/inbox`) is not yet implemented. |
| **LinkedIn Gateway** | Gateway / Ingestion | Opaque reference | **Stubbed** — Channel `"linkedin"` recognized in contracts and DB tables, but transport is unbound (`delivery_transport_unbound`) and scraping (`cli/sense_jobs.py`) is missing. |
| **Dex API** | `api.prod.getdex.com/v1` | Bearer Token (`DEX_API_KEY`) | **Implemented** — Cursor-based pagination over 2,252 contacts in `core/dex_client.py`. |

---

### 1.5 Verification Infrastructure & Test Suites

* **Existing Test Inventory (`tests/`, 30 test files)**:
  * `tests/test_sources_dex_delta.py` (163 lines): Ingestion & delta proofing.
  * `tests/test_sources_gmail.py` (207 lines): Gmail sweep & OAuth refresh token exchange.
  * `tests/test_k0s_gmail_sense.py` (25 lines): Manifest assertion for CronJob secrets.
  * `tests/test_jobsearch_executors.py` (1,006 lines): Command executor unit tests.
  * `tests/test_jobsearch_scoring.py` (274 lines): Deterministic scoring rules & employer exclusions.
  * `tests/test_jobsearch_intent.py` (608 lines): Intent setting, persistence, and rescoring.
  * `tests/test_graphql_jobsearch.py` (850 lines): GraphQL query projection tests.
  * `tests/conftest.py`: In-memory SQLite session, FakeRedis, FakeJobSearchPublisher, ReceiptIssuer fixture.

* **Missing Test Suites (Required by Acceptance Criteria line 38)**:
  * `tests/test_jobsearch_profile.py` — MISSING
  * `tests/test_jobsearch_copilot.py` — MISSING
  * `tests/test_jobsearch_messaging.py` — MISSING
  * `tests/test_jobsearch_calendar.py` — MISSING
  * `tests/test_jobsearch_gjallarhorn.py` — MISSING

---

## 2. Logic Chain

1. **Premise 1 (Container Readiness)**: Both Dockerfiles (`Dockerfile` and `apps/web/Dockerfile`) are functional and buildable, but require exact tag names `ccc/ultradex:dev` and `ccc/glass:dev` to match `deploy/k0s/ccc.yaml`.
2. **Premise 2 (Deployment Target)**: The deployment manifest `deploy/k0s/ccc.yaml` targets namespace `ccc-tmp` on `vakr` (`10.10.20.101`) with NodePort 30808 for Glass UI and NodePort 30800 for the API.
3. **Premise 3 (Live Injection Mechanics)**: On `vakr`, k0s uses containerd with `imagePullPolicy: Never`. Images must be pushed into k0s via `k0s ctr images import`. An automated deployment script is required to execute build, image transfer, secret injection, manifest application, and pod readiness checks.
4. **Premise 4 (Integration & Mock Requirements)**:
   - For offline test hermeticity, external integrations (Mosquitto `ratatoskr:1883`, Gjallarhorn `ratatoskr:18099`, Google Calendar, Gmail Send, LinkedIn) must provide clean mock transports/adapters in unit tests while supporting real endpoint configuration in deployment.
   - Seed data fixtures (2,252 Dex contacts, candidate profile, 40+ CTO skills, target roles, sample leads) should be readily loadable via a single seed command/script.

---

## 3. Caveats

1. **Hardware & Tailscale Connectivity**: `vakr` (`10.10.20.101`) is an internal node on Nate's network (reachable via SSH `vakr-svc` or direct IP when on network/Tailscale).
2. **External Endpoints**: `ratatoskr:1883` and `ratatoskr:18099` are live fleet services on the internal network; in CI/test environments, tests must use mock transports (e.g. `unittest.mock` / fake async handlers) to remain 100% hermetic.
3. **Contracts Package Version**: `requirements.txt` specifies `ravenhelm-contracts==0.5.0` which is installed from the private Forgejo PyPI index at `http://hrafngud.ravenmask.net:3300/api/packages/nate/pypi/simple/`.

---

## 4. Conclusion

The deployment and verification infrastructure has a solid architectural base (`deploy/k0s/ccc.yaml`, Dockerfiles, `conftest.py` test harness), with clear next steps required for complete delivery:

1. **Docker & Deployment Automation**:
   - Add a deployment script (e.g. `scripts/deploy-k0s.sh`) to build `ccc/ultradex:dev` and `ccc/glass:dev`, transfer & import into k0s on `vakr`, create `ultradex` and `gmail-sense` secrets in `ccc-tmp`, apply `deploy/k0s/ccc.yaml`, and verify rollout.
2. **Seed Data & Fixtures**:
   - Provide offline seed fixtures for 2,252 Dex contacts, Nate Walker resume / 40+ CTO skills taxonomy / target roles / comp expectations ($180k/$250k), and sample employer leads.
3. **Integration Adapters & Clients**:
   - Implement Mosquitto MQTT client (`ratatoskr:1883`) and Gjallarhorn ASR integration (`ratatoskr:18099`) with debrief extraction and Obsidian notes export.
   - Implement Google Calendar slot sensing (09:00–17:00 CT) and 3-pill availability injection.
   - Implement in-app Gmail API and LinkedIn dispatchers.
4. **Verification Test Harness**:
   - Implement the 5 missing pytest suites: `test_jobsearch_profile.py`, `test_jobsearch_copilot.py`, `test_jobsearch_messaging.py`, `test_jobsearch_calendar.py`, `test_jobsearch_gjallarhorn.py`.
   - Add end-to-end deployment verification checking `http://10.10.20.101:30808/` and `http://10.10.20.101:30800/health`.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Dockerfiles and Build Context**:
   ```bash
   docker build -t ccc/ultradex:dev -f Dockerfile .
   docker build -t ccc/glass:dev -f apps/web/Dockerfile .
   ```

2. **Verify k0s Manifest Integrity**:
   ```bash
   kubectl --dry-run=client apply -f deploy/k0s/ccc.yaml
   ```

3. **Verify Existing Tests**:
   ```bash
   pytest tests/test_sources_dex_delta.py tests/test_sources_gmail.py tests/test_k0s_gmail_sense.py tests/test_jobsearch_executors.py tests/test_jobsearch_scoring.py tests/test_jobsearch_intent.py
   ```

4. **Verify Missing Test Suites**:
   ```bash
   ls tests/test_jobsearch_profile.py tests/test_jobsearch_copilot.py tests/test_jobsearch_messaging.py tests/test_jobsearch_calendar.py tests/test_jobsearch_gjallarhorn.py
   ```
   *Expected*: Files do not exist yet (confirming task backlog).
