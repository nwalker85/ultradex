# Original User Request

## Initial Request — 2026-08-24T06:36:36Z

Implement the Career Command Center Job-Search CRM and Operating System, unifying candidate profile matching, dynamic job scraping, complete CRM pipeline management (Contacts, Organizations, Leads, Opportunities, Applications), Copilot Next Best Actions with 3-pill recruiter replies, in-app Gmail/LinkedIn messaging, Google Calendar integration, and sovereign meeting transcription via Gjallarhorn ASR and Mosquitto MQTT.

Working directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req
Integrity mode: development

## Requirements

### R1. Candidate Profile & Dynamic Sourcing Engine
* Establish the authoritative candidate profile store (`/profile`) seeded with Nate Walker's resume, 40+ CTO skills taxonomy (Expert/Advanced), production ML depth, target roles, and compensation expectations.
* Implement dynamic job sourcing in `cli/sense_jobs.py` that queries target roles and domains from `/profile` to scrape and score postings from LinkedIn and target employer career boards (Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS).

### R2. Complete CRM Domain & Pipeline Lifecycle
* Implement database schemas, ORM models, GraphQL APIs, TypeScript SDK, and Svelte Glass UI views for:
  * **Contacts** (`/contacts`, `/contacts/[id]`): 2,252 Dex contacts with CRM profile, advocacy score, and communication history.
  * **Organizations** (`/organizations`, `/organizations/[id]`): Employer directory aggregating contacts, open leads, and opportunities.
  * **Leads** (`/leads`, `/leads/[id]`): Unapplied job postings with profile match breakdown and one-click "Apply / Convert to Opportunity".
  * **Opportunities** (`/opportunities`, `/opportunities/[id]`): Active pipeline pursuits with stage trackers and connected contacts.
  * **Applications** (`/applications`, `/applications/[id]`): Formal stage progression tracking.
  * **Relationships** (`/relationships`): Clean table (Name -> Organization -> Role -> Context).

### R3. Copilot Engine & Omnichannel In-App Messaging
* Surface prioritized **Next Best Actions** on the Command Home (`/`) rail.
* Implement a 3-pill recruiter response generator (*1. Accept & Share Availability*, *2. Request Scope & Comp Details*, *3. Polite Pass*) for inbound messages, automatically injecting live open availability from Google Calendar.
* Implement in-app message composer and dispatcher (`/inbox`, `/contacts/[id]`) supporting direct sending via Gmail API (landing in standard Gmail Sent folder) and LinkedIn gateway.

### R4. Google Calendar & Sovereign Voice Engine (Gjallarhorn + MQTT)
* Integrate Google Calendar sensing to detect scheduled interview rounds and compute open 30-min/45-min slots during working hours (09:00–17:00 CT).
* Connect to Mosquitto MQTT broker on `ratatoskr:1883` and Gjallarhorn ASR (`ratatoskr:18099`) to record/stream interview audio, extract structured debriefs (Executive Summary, Questions Asked, Action Items), auto-populate Command Home action items, and export formatted notes to local Obsidian vault (`~/docs/40-personal/interviews/`).

## Acceptance Criteria

### Backend & Core Services
- [ ] Database migrations execute cleanly for all CRM, messaging, calendar, and interview tables.
- [ ] `pytest tests/test_jobsearch_executors.py tests/test_jobsearch_profile.py tests/test_jobsearch_copilot.py tests/test_jobsearch_messaging.py tests/test_jobsearch_calendar.py tests/test_jobsearch_gjallarhorn.py` pass with 100% success.
- [ ] Ingested job postings and recruiter emails correctly score against the Profile taxonomy.
- [ ] Converting a Lead creates an active Opportunity and initial Application record.

### API & TypeScript SDK
- [ ] GraphQL queries and mutations for Profile, Leads, Organizations, Contacts, Messages, Next Best Actions, Calendar Events, and Interview Debriefs return validated schemas.
- [ ] `npm test --workspace=@ultradex/sdk` passes with zero type errors.

### Frontend Glass SvelteKit App
- [ ] `npm test --workspace=ccc-glass` passes all unit and component tests.
- [ ] All 10 routes render with accessible contrast and interactive controls (`/`, `/inbox`, `/leads`, `/leads/[id]`, `/opportunities`, `/opportunities/[id]`, `/applications`, `/contacts`, `/contacts/[id]`, `/organizations`, `/organizations/[id]`, `/relationships`, `/profile`, `/settings`).
- [ ] Left navigation reflects the full CRM suite.

### Deployment & Live Verification
- [ ] Docker images for backend (`ccc/ultradex:dev`) and frontend (`ccc/glass:dev`) build and import into `k0s` on `vakr` (`10.10.20.101`).
- [ ] Pods rollout cleanly in `ccc-tmp` namespace and live UI is verified at `http://10.10.20.101:30808/`.
