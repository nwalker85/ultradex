# YC Austin and US-Remote Job Feed Watch Design

**Status:** Written review  
**Concept approved:** Nate Walker, 2026-07-23  
**Work unit:** JS-U04a, bounded child of JS-U04 source adapters

## Purpose

Add Y Combinator's Austin and US-remote startup job feeds as a durable Ultradex source. The watcher discovers and normalizes every public listing, deduplicates overlap, submits the results through the governed job-search control surface, and immediately raises an operator alert when the separate scoring command identifies an exceptional match.

The watcher is a source adapter, not an alternate job tracker. It does not own opportunity truth, scoring policy, outreach, or application state.

## Scope

### Watched views

The source identity is `yc_jobs` with two views:

- `yc_jobs:austin`: [Jobs at Y Combinator startups in Austin](https://www.ycombinator.com/jobs/role/all/austin)
- `yc_jobs:remote_us`: [Remote jobs at Y Combinator startups](https://www.ycombinator.com/jobs/role/all/remote), filtered after extraction to listings whose normalized location explicitly permits `Remote (US)` or an equivalent United States remote scope.

The operator-facing saved query remains the original [Work at a Startup Austin search](https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any&industry=any&interviewProcess=any&jobType=any&layout=list-compact&locations=Austin%2C%20TX%2C%20US&sortBy=created_desc&tab=any&usVisaNotRequired=any). It is evidence of user intent, not the automated extraction endpoint.

### Included

- Public, unauthenticated YC job pages.
- Austin roles and roles explicitly available remotely in the United States.
- Hourly scheduled refresh and an operator-initiated manual refresh.
- Normalization, cross-view deduplication, material-change detection, disappearance handling, and source health.
- Governed ingestion, opportunity scoring, exceptional-match event emission, and alert-delivery evidence.
- Redacted telemetry, audit correlation, saved sanitized fixtures, and parser-regression tests.

### Excluded

- Authenticated Work at a Startup pages, cookies, private recommendations, profiles, or application flows.
- Browser automation as a normal extraction path.
- Automated application submission, LinkedIn automation, or outbound messaging.
- Job-description bodies in telemetry, receipts, logs, or Prometheus labels.
- Role-specific scoring logic inside the YC adapter.
- A new notification transport. Delivery consumes the canonical exceptional-match event through the operator notification route owned by JS-U06/JS-U07.

## Source and policy boundary

As verified on 2026-07-23, Y Combinator's published `robots.txt` allows the public `/jobs` routes. The adapter:

- identifies itself with a stable Ravenhelm/Ultradex user agent and contact URL;
- uses conditional requests when the server exposes `ETag` or `Last-Modified`;
- limits normal polling to one request per view per hour;
- honors `Retry-After`;
- applies bounded exponential backoff with jitter for `429` and transient `5xx` responses;
- never bypasses authentication, anti-bot controls, or access restrictions;
- disables the affected view and emits a policy finding if published policy later disallows it.

Browser-assisted capture is a manual evidence path only. It cannot silently replace the public HTTP adapter.

## Authority and execution path

```text
hourly scheduler / manual SDK caller
                |
      official Ultradex Python SDK
                |
       sources.ingest command
                |
       Gateway acceptance/refusal
                |
      NATS task -> YC adapter executor
                |
 normalized source facts + lifecycle events + receipt
                |
 opportunity projection -> opportunities.score command
                |
 exceptional match event -> operator notification executor
```

- Scheduled and manual refreshes use the same `sources.ingest` command contract.
- The SDK is the only supported client boundary.
- Command acceptance returns a `ContractHandle`; it does not claim extraction completion.
- The adapter executor emits lifecycle events and a durable receipt for success, partial success, refusal, or failure.
- Projection updates and scoring occur from immutable facts, not inside the API handler.
- Notification delivery produces its own terminal event and receipt correlated to the exceptional-match event.

## Source configuration

Each view has immutable identity plus versioned behavior:

| Field | Austin | US remote |
|---|---|---|
| `source_id` | `yc_jobs` | `yc_jobs` |
| `view_id` | `austin` | `remote_us` |
| `source_kind` | `public_web` | `public_web` |
| `cadence` | hourly | hourly |
| `location_scope` | Austin, Texas, United States | Remote, United States |
| `parser_version` | adapter release identity | adapter release identity |

Runtime configuration may change cadence or disable a view, but it cannot change source identity, relax the location boundary, or enable authenticated extraction.

## Normalized record

The adapter emits one normalized record per job version:

- canonical YC job URL;
- YC job identifier when present;
- company name and canonical company URL;
- YC batch when present;
- role title;
- YC role category and specialization when present;
- normalized employment type;
- normalized location strings;
- `allows_austin`;
- `allows_remote_us`;
- normalized compensation minimum, maximum, currency, and period when present;
- equity availability when explicitly present;
- public posting age or posting timestamp when present;
- first-seen and last-seen timestamps;
- source view identities;
- parser version;
- bounded content commitment;
- opaque evidence reference.

Missing fields remain absent. The adapter does not infer compensation, seniority, remote eligibility, or employment type from unsupported text.

## Deduplication and versioning

1. Prefer the canonical YC job URL as the stable opportunity key.
2. If the URL lacks a stable identifier, use a versioned commitment over canonical company URL, normalized title, normalized location scope, and source namespace.
3. Merge Austin and US-remote sightings into one record while retaining both view identities.
4. Compute a material-change commitment from normalized decision-relevant fields. Cosmetic HTML changes do not create a new version.
5. Reprocessing the same source version is idempotent and produces no duplicate opportunity or alert.
6. A material change creates a new source version and re-runs scoring.

The raw fetched document may exist in a short-lived, access-controlled forensic cache for parser diagnosis. It is not part of the projection, routine receipt, or telemetry record and expires within 24 hours.

## Lifecycle and disappearance

Each listing moves through computed source states:

- `active`: observed in the latest successful eligible view refresh;
- `suspect_missing`: absent from one or two consecutive successful refreshes;
- `closed`: absent from three consecutive successful refreshes across every eligible view;
- `source_unavailable`: source freshness cannot be established because refreshes failed.

Failed, refused, policy-disabled, or parser-invalid refreshes do not increment the missing counter. Closure is a projection from successful observations, never an assertion made by the fetcher.

## Scoring and exceptional matches

The YC adapter submits normalized facts and then requests the governed `opportunities.score` command. It does not contain career-fit weights.

An exceptional match satisfies all of the following:

- fit score is at least `85`;
- opportunity state is active;
- location permits Austin or remote work in the United States;
- no disqualifying risk flag is present;
- the role version has not already produced a successful exceptional alert.

Compensation may increase or reduce fit but is not a required field. Missing compensation cannot independently disqualify a role.

The scorer returns a bounded explanation and risk flags. Source text, resume text, prompts, and model completions remain in their designated custody systems.

## Immediate alert behavior

On the first exceptional result for a role version, the scorer emits `jobsearch.match.exceptional.v1`. The event includes:

- opportunity and source-version references;
- employer and role title;
- fit score;
- bounded fit explanation;
- location and compensation summary;
- canonical public job URL;
- correlation, causation, operation, contract, execution, trace, and audit references.

The event contains enough normalized information for a concise operator alert without fetching restricted content.

Alerting is at-most-once per successfully delivered role version from the operator's perspective:

- an idempotency key binds opportunity, source version, scoring-policy version, and operator;
- delivery retries use the same key;
- a failed delivery remains retryable and visible;
- a successful delivery suppresses duplicates;
- a materially changed role may alert again only after re-scoring at or above the exceptional threshold.

JS-U04a owns correct event emission. JS-U06/JS-U07 own the configured operator delivery transport, delivery receipt, and user-visible alert. Until a delivery transport is configured and proven, the watcher reports a Broken Binding and cannot claim end-to-end immediate alerting.

## Error handling

- `304 Not Modified`: successful no-change refresh with updated watcher heartbeat.
- `429`: honor `Retry-After`; otherwise bounded exponential backoff with jitter.
- transient `5xx` or network failure: retry within the task budget, then fail with a structured receipt.
- permanent `4xx`: refuse further retries for that task and open a source-policy/configuration finding.
- zero parsed jobs with a non-empty response: parser-regression failure, not a successful empty feed.
- partial parse: emit accepted records plus a partial-success receipt with bounded error counts and evidence references.
- unexpected location text: retain the source string, exclude it from US-remote eligibility, and emit a bounded normalization finding.
- policy or robots change: disable automated retrieval for the affected view pending operator review.

No failure path archives opportunities or fabricates freshness.

## Observability and audit

### Watcher intent

| Concern | Watcher -> Verb -> Entity | Primary evidence |
|---|---|---|
| Availability | Job Search Operations -> watches -> YC source view | last successful refresh and terminal receipt |
| Performance | Job Search Operations -> measures -> YC ingestion task | fetch, parse, projection, and scoring durations |
| Security | Private Estate Security -> audits -> YC adapter | authenticated-access attempts and policy findings |
| Governance | Job Search Governance -> verifies -> ingestion operation | contract, event, receipt, and evidence-reference coverage |
| Cost | Job Search Operations -> measures -> YC scoring run | bounded model invocation count, tokens, and cost |

### Bounded telemetry

Metrics use bounded labels such as source, view, result, parser version, and environment:

- `ultradex_jobsearch_source_refresh_total`
- `ultradex_jobsearch_source_refresh_duration_seconds`
- `ultradex_jobsearch_source_records_total`
- `ultradex_jobsearch_source_parse_errors_total`
- `ultradex_jobsearch_source_last_success_timestamp_seconds`
- `ultradex_jobsearch_source_projection_lag_seconds`
- `ultradex_jobsearch_exceptional_matches_total`
- `ultradex_jobsearch_exceptional_alert_delivery_total`
- `ultradex_jobsearch_missing_receipts_total`

Opportunity identifiers, URLs, company names, role titles, correlation identifiers, and evidence references are forbidden as metric labels. They remain in structured, access-controlled logs and audit records.

### Required alerts

- no successful refresh for more than three scheduled intervals;
- parser returns zero records from a non-empty response;
- projection lag exceeds two scheduled intervals;
- accepted task lacks a terminal event or valid receipt;
- exceptional-match event lacks successful delivery evidence after its retry budget;
- policy boundary or redaction violation;
- watcher heartbeat is missing.

## Privacy and custody

- Classification is `private`, `operator-only`.
- Public job facts may be normalized into projections.
- Raw page captures use forensic custody and expire within 24 hours.
- Routine logs contain counts, states, hashes, and opaque references, not page bodies.
- Alert payloads contain only the bounded normalized facts required for action.
- Gmail, LinkedIn, Dex, resume, and outreach content are outside this adapter's custody.

## Test strategy

Sanitized, versioned HTML fixtures cover:

- Austin-only role;
- US-remote-only role;
- duplicate role present in both feeds;
- new role;
- unchanged role;
- materially changed role;
- cosmetic HTML change;
- one, two, and three successful misses;
- source failure between misses;
- missing compensation;
- ambiguous remote location;
- malformed card among valid cards;
- non-empty response producing zero records;
- `304`, `429`, transient `5xx`, and permanent `4xx`;
- policy-disabled source;
- repeated task and repeated exceptional-match event;
- alert failure followed by successful idempotent retry;
- telemetry redaction and metric-label cardinality guards;
- missing terminal event and missing receipt detection.

Contract fixtures prove the SDK request, Gateway acceptance/refusal, NATS task, normalized event, projection, scoring request, exceptional-match event, and receipts preserve the canonical correlation context.

## Acceptance criteria

1. One SDK command refreshes both configured views or either selected view and returns a `ContractHandle`.
2. Scheduled refresh runs hourly; manual refresh uses the same command and executor.
3. Only Austin and explicitly US-remote roles enter the eligible opportunity projection.
4. Cross-view overlap produces one opportunity with both source views.
5. Replaying an unchanged version produces no duplicate opportunity, score, or alert.
6. Material changes produce a new version and re-run scoring.
7. Three consecutive successful misses are required before closure.
8. Failed or policy-disabled refreshes never close a role or fabricate freshness.
9. Exceptional matches emit exactly one canonical event per role version and scoring-policy version.
10. End-to-end immediate alerting is not claimed until delivery evidence exists; missing delivery is a Broken Binding and an alertable condition.
11. Every accepted mutation has lifecycle events, a terminal state, and a valid receipt.
12. Telemetry passes redaction and bounded-cardinality tests.
13. Saved fixtures exercise all documented extraction and failure paths without live YC access.
14. Public-path policy is checked at implementation and recorded in the source manifest.

## Delivery boundary

JS-U04a may begin only after JS-U03's governed commands and executors are merged. Its implementation PR may add:

- YC source manifest and parser;
- source adapter port and executor;
- normalized fixtures and tests;
- scheduler registration through the official command path;
- exceptional-match event emission integration;
- source health instrumentation and runbook material specific to this adapter.

It may not add a raw client path, authenticated scraping, role-fit weights, outreach behavior, or an ungoverned notification sender.
