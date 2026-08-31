# Career CRM Relational Schema Design

- **Status:** Draft
- **Maturity:** Informational
- **Decision:** Target schema captured for review; implementation and migration
  are not authorized
- **Version:** v0.1.0-draft
- **Date:** 2026-08-31
- **Owner:** Nate Walker
- **Product:** Career Command Center / Ultradex

## Purpose

Define the target PostgreSQL schema for Career Command Center as a career CRM.
Its core lifecycle is the same as a sales CRM:

```text
Lead -> conversion -> Opportunity -> Closed Won / Closed Lost
```

Employment and contract pursuits use the same `Opportunity` aggregate and the
same funnel. `opportunity_type` changes type-specific terms and the evidence
required to close an opportunity as won; it does not select a different
pipeline.

This design revises the domain-entity boundaries in the earlier
[Job Search Intelligence Platform Design](2026-07-22-job-search-platform-design.md).
It does not replace that document's command, SDK, privacy, audit, or custody
architecture. The current database, the target database, and any migration
plan must remain explicitly separate.

## Core decisions

1. `Lead` is an unqualified signal.
2. Lead conversion creates or reuses an organization and contact, then creates
   an opportunity.
3. One opportunity represents one specific pursuit at one or more related
   organizations.
4. Employment and contract pursuits share one opportunity model and stage
   taxonomy.
5. An application, proposal, or RFP response is a child submission, not a
   second pipeline root.
6. `Organization` is the canonical organization aggregate. A company is a kind
   of organization, not a separate aggregate.
7. Organization and contact roles are contextual to an opportunity.
8. Communications, calendar events, documents, and external records retain
   provenance and link to canonical CRM records.
9. `Action` is a first-class object. A workspace has at most one authoritative
   next-best-action pointer at a time.
10. Integration deletion never cascades into canonical CRM data.

## Schema conventions

- Primary keys are UUIDs.
- Every workspace-owned table carries `workspace_id` for ownership and row-level
  security.
- Canonical entity records carry `created_at`, `updated_at`, and nullable
  `deleted_at`. Subordinate records are either append-only or have an explicit
  lifecycle status.
- Monetary values use `numeric` plus an ISO 4217 `currency` column.
- Stage history, score snapshots, source-record versions, and document versions
  are append-only.
- External provider identifiers are never canonical entity identifiers.
- Raw private content remains in its designated custody system. PostgreSQL stores
  bounded metadata, commitments, redacted summaries, and opaque content
  references unless a separate custody decision explicitly authorizes content
  storage.
- Foreign keys default to `RESTRICT`. Cascading deletes are limited to subordinate
  join rows and never cross from an integration account into canonical CRM data.

## 1. Workspace ownership

```text
workspaces
- id uuid PK
- name text NOT NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
```

Every user-owned record belongs to exactly one workspace.

## 2. Organizations and contacts

### Organizations

```text
organizations
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- name text NOT NULL
- kind text NOT NULL
- website_url text NULL
- linkedin_url text NULL
- description text NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
- deleted_at timestamptz NULL
```

Initial `kind` values are `company`, `nonprofit`, `government`, `school`,
`association`, and `other`. Employer, client, agency, and partner are not
organization kinds; they are roles played in a particular opportunity.

```text
organization_domains
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- organization_id uuid NOT NULL FK -> organizations
- domain text NOT NULL
- normalized_domain text NOT NULL
- is_primary boolean NOT NULL DEFAULT false
- UNIQUE(workspace_id, normalized_domain)

organization_aliases
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- organization_id uuid NOT NULL FK -> organizations
- alias text NOT NULL
- normalized_alias text NOT NULL
- UNIQUE(organization_id, normalized_alias)
```

### Contacts

```text
contacts
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- first_name text NULL
- last_name text NULL
- headline text NULL
- linkedin_url text NULL
- notes text NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
- deleted_at timestamptz NULL

contact_channels
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- contact_id uuid NOT NULL FK -> contacts
- channel_type text NOT NULL
- value text NOT NULL
- normalized_value text NOT NULL
- is_primary boolean NOT NULL DEFAULT false
- UNIQUE(workspace_id, channel_type, normalized_value)

contact_organization_affiliations
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- contact_id uuid NOT NULL FK -> contacts
- organization_id uuid NOT NULL FK -> organizations
- title text NULL
- department text NULL
- started_at date NULL
- ended_at date NULL
- is_current boolean NOT NULL DEFAULT true
```

Initial `channel_type` values are `email`, `phone`, and `linkedin`.

A contact can belong to multiple organizations over time. The schema therefore
does not place `organization_id` directly on `contacts`.

## 3. Leads and conversion

A lead preserves the source signal before it has been qualified or resolved
against canonical CRM records.

```text
leads
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- status text NOT NULL
- person_name text NULL
- organization_name text NULL
- title text NULL
- email text NULL
- source_type text NOT NULL
- source_url text NULL
- summary text NULL
- discovered_at timestamptz NOT NULL
- qualified_at timestamptz NULL
- disqualified_reason text NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
- deleted_at timestamptz NULL
```

Initial lead statuses are `new`, `nurturing`, `qualified`, `disqualified`, and
`converted`.

```text
lead_conversions
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- lead_id uuid NOT NULL FK -> leads
- organization_id uuid NOT NULL FK -> organizations
- contact_id uuid NOT NULL FK -> contacts
- opportunity_id uuid NOT NULL FK -> opportunities
- converted_at timestamptz NOT NULL
- UNIQUE(lead_id)
```

Conversion is atomic: resolve or create the canonical organization and contact,
create the opportunity, record the conversion, and transition the lead to
`converted` in one transaction.

## 4. Shared opportunity funnel

```text
pipelines
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- code text NOT NULL
- name text NOT NULL
- UNIQUE(workspace_id, code)

pipeline_stages
- id uuid PK
- pipeline_id uuid NOT NULL FK -> pipelines
- code text NOT NULL
- name text NOT NULL
- ordinal integer NOT NULL
- outcome text NULL
- UNIQUE(pipeline_id, code)
- UNIQUE(pipeline_id, ordinal)

opportunities
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- pipeline_id uuid NOT NULL FK -> pipelines
- stage_id uuid NOT NULL FK -> pipeline_stages
- opportunity_type text NOT NULL
- name text NOT NULL
- role_title text NULL
- description text NULL
- opened_at timestamptz NOT NULL
- expected_close_date date NULL
- probability numeric(5,2) NULL
- closed_at timestamptz NULL
- lost_reason text NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
- deleted_at timestamptz NULL
```

`opportunity_type` is constrained to `employment` or `contract`. `outcome` is
nullable for open stages and constrained to `won` or `lost` for terminal stages.
A composite foreign key ensures that an opportunity's `stage_id` belongs to its
`pipeline_id`.

Career Command Center seeds one shared career-opportunity pipeline. Both
opportunity types reference it.

### Opportunity organizations

```text
opportunity_organizations
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- organization_id uuid NOT NULL FK -> organizations
- role text NOT NULL
- is_primary boolean NOT NULL DEFAULT false
- PRIMARY KEY(opportunity_id, organization_id, role)
```

Initial roles are `employer`, `client`, `agency`, `consultancy`, `partner`, and
`other`. A partial unique index permits at most one primary organization per
opportunity and role.

### Opportunity contacts

```text
opportunity_contacts
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- contact_id uuid NOT NULL FK -> contacts
- role text NOT NULL
- influence_level text NULL
- relationship_strength integer NULL
- is_primary boolean NOT NULL DEFAULT false
- PRIMARY KEY(opportunity_id, contact_id, role)
```

Initial roles include `recruiter`, `hiring_manager`, `champion`,
`decision_maker`, `economic_buyer`, and `other`.

### Stage history

```text
opportunity_stage_history
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- from_stage_id uuid NULL FK -> pipeline_stages
- to_stage_id uuid NOT NULL FK -> pipeline_stages
- changed_at timestamptz NOT NULL
- reason text NULL
```

The current stage is stored on `opportunities`; the immutable history is the
audit trail for how it reached that stage.

## 5. Type-specific opportunity details

```text
employment_opportunity_details
- opportunity_id uuid PK/FK -> opportunities
- workspace_id uuid NOT NULL FK -> workspaces
- employment_type text NULL
- location text NULL
- remote_policy text NULL
- requisition_id text NULL
- job_posting_url text NULL
- compensation_min numeric NULL
- compensation_max numeric NULL
- currency char(3) NULL

contract_opportunity_details
- opportunity_id uuid PK/FK -> opportunities
- workspace_id uuid NOT NULL FK -> workspaces
- engagement_model text NULL
- rate numeric NULL
- rate_unit text NULL
- estimated_value numeric NULL
- currency char(3) NULL
- expected_start_date date NULL
- expected_end_date date NULL
```

Initial contract engagement models are `direct`, `corp_to_corp`, and
`subcontract`. Initial rate units are `hour`, `day`, `month`, and `fixed`.

A deferred constraint trigger enforces exactly one matching detail record:

- `employment` opportunities have one employment detail row and no contract
  detail row.
- `contract` opportunities have one contract detail row and no employment detail
  row.

## 6. Submissions and close evidence

An application or proposal is a child milestone under an opportunity.

```text
submissions
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- submission_type text NOT NULL
- channel text NULL
- submitted_at timestamptz NULL
- status text NOT NULL
- external_reference text NULL
- notes text NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
```

Initial submission types are `application`, `proposal`, and `rfp_response`.

### Employment offers

```text
employment_offers
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- offered_at timestamptz NOT NULL
- compensation numeric NULL
- currency char(3) NULL
- start_date date NULL
- status text NOT NULL
- accepted_at timestamptz NULL
```

Initial statuses are `received`, `negotiating`, `accepted`, and `declined`.

### Contract agreements

```text
contract_agreements
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- agreement_type text NOT NULL
- value numeric NULL
- currency char(3) NULL
- status text NOT NULL
- executed_at timestamptz NULL
```

Initial agreement types are `contract`, `sow`, and `subcontract`; initial
statuses are `draft`, `sent`, `executed`, and `rejected`.

A deferred close constraint enforces:

- Employment cannot enter a Closed Won stage without an accepted employment
  offer.
- Contract cannot enter a Closed Won stage without an executed contract
  agreement.

## 7. Communications and calendar

```text
interaction_threads
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- channel text NOT NULL
- subject text NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL

interactions
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- thread_id uuid NULL FK -> interaction_threads
- interaction_type text NOT NULL
- direction text NULL
- subject text NULL
- redacted_summary text NULL
- content_ref text NULL
- content_commitment text NULL
- occurred_at timestamptz NOT NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
```

Initial interaction types are `email`, `linkedin_message`, `meeting`, `call`, and
`note`.

```text
interaction_contacts
- workspace_id uuid NOT NULL FK -> workspaces
- interaction_id uuid NOT NULL FK -> interactions
- contact_id uuid NOT NULL FK -> contacts
- participant_role text NOT NULL
- PRIMARY KEY(interaction_id, contact_id, participant_role)

interaction_opportunities
- workspace_id uuid NOT NULL FK -> workspaces
- interaction_id uuid NOT NULL FK -> interactions
- opportunity_id uuid NOT NULL FK -> opportunities
- PRIMARY KEY(interaction_id, opportunity_id)

interaction_organizations
- workspace_id uuid NOT NULL FK -> workspaces
- interaction_id uuid NOT NULL FK -> interactions
- organization_id uuid NOT NULL FK -> organizations
- PRIMARY KEY(interaction_id, organization_id)

calendar_events
- interaction_id uuid PK/FK -> interactions
- workspace_id uuid NOT NULL FK -> workspaces
- starts_at timestamptz NOT NULL
- ends_at timestamptz NOT NULL
- location text NULL
- meeting_url text NULL
```

One email or meeting can link to multiple contacts and also roll up to an
opportunity and one or more organizations.

## 8. Integration provenance

```text
integration_accounts
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- provider text NOT NULL
- external_account_id text NOT NULL
- status text NOT NULL
- last_synced_at timestamptz NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
- UNIQUE(workspace_id, provider, external_account_id)

sync_runs
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- integration_account_id uuid NOT NULL FK -> integration_accounts
- started_at timestamptz NOT NULL
- completed_at timestamptz NULL
- status text NOT NULL
- cursor text NULL
- records_seen integer NOT NULL DEFAULT 0
- records_created integer NOT NULL DEFAULT 0
- records_updated integer NOT NULL DEFAULT 0
- error_summary text NULL

source_records
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- integration_account_id uuid NOT NULL FK -> integration_accounts
- object_type text NOT NULL
- external_id text NOT NULL
- first_seen_at timestamptz NOT NULL
- last_seen_at timestamptz NOT NULL
- UNIQUE(integration_account_id, object_type, external_id)

source_record_versions
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- source_record_id uuid NOT NULL FK -> source_records
- content_ref text NULL
- content_commitment text NULL
- normalized_metadata jsonb NOT NULL DEFAULT '{}'
- content_fingerprint text NOT NULL
- observed_at timestamptz NOT NULL
- UNIQUE(source_record_id, content_fingerprint)
```

Typed provenance links retain foreign-key integrity:

```text
organization_source_records
- organization_id uuid FK -> organizations
- source_record_id uuid FK -> source_records
- PRIMARY KEY(organization_id, source_record_id)

contact_source_records
- contact_id uuid FK -> contacts
- source_record_id uuid FK -> source_records
- PRIMARY KEY(contact_id, source_record_id)

lead_source_records
- lead_id uuid FK -> leads
- source_record_id uuid FK -> source_records
- PRIMARY KEY(lead_id, source_record_id)

interaction_source_records
- interaction_id uuid FK -> interactions
- source_record_id uuid FK -> source_records
- PRIMARY KEY(interaction_id, source_record_id)

opportunity_source_records
- opportunity_id uuid FK -> opportunities
- source_record_id uuid FK -> source_records
- PRIMARY KEY(opportunity_id, source_record_id)
```

A Dex-discovered LinkedIn organization is represented as:

```text
integration_accounts(provider = dex)
  -> source_records(object_type = linkedin_organization)
  -> organization_source_records
  -> organizations
```

This chain makes creation provenance queryable and allows source data to be
reprocessed without treating Dex or LinkedIn identifiers as the canonical
organization key.

## 9. Documents and immutable versions

```text
documents
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- document_type text NOT NULL
- name text NOT NULL
- status text NOT NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
- deleted_at timestamptz NULL

document_versions
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- document_id uuid NOT NULL FK -> documents
- version_number integer NOT NULL
- storage_key text NOT NULL
- media_type text NOT NULL
- sha256 text NOT NULL
- created_at timestamptz NOT NULL
- UNIQUE(document_id, version_number)
- UNIQUE(workspace_id, sha256)
```

Initial document types are `resume`, `cover_letter`, `job_description`, `offer`,
`contract`, `sow`, and `other`.

```text
opportunity_documents
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- document_version_id uuid NOT NULL FK -> document_versions
- role text NOT NULL
- PRIMARY KEY(opportunity_id, document_version_id, role)

submission_documents
- workspace_id uuid NOT NULL FK -> workspaces
- submission_id uuid NOT NULL FK -> submissions
- document_version_id uuid NOT NULL FK -> document_versions
- role text NOT NULL
- PRIMARY KEY(submission_id, document_version_id, role)
```

Submissions reference immutable document versions so later edits do not change
the historical record of what was submitted.

## 10. MEDDPICC qualification and evidence

```text
opportunity_qualification
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- opportunity_id uuid NOT NULL FK -> opportunities
- dimension text NOT NULL
- status text NOT NULL
- score numeric NULL
- notes text NULL
- validated_at timestamptz NULL
- updated_at timestamptz NOT NULL
- UNIQUE(opportunity_id, dimension)
```

Initial dimensions are `metrics`, `economic_buyer`, `decision_criteria`,
`decision_process`, `paper_process`, `identify_pain`, `champion`, and
`competition`. Initial statuses are `unknown`, `weak`, `developing`, and
`validated`.

```text
qualification_evidence
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- qualification_id uuid NOT NULL FK -> opportunity_qualification
- interaction_id uuid NULL FK -> interactions
- document_version_id uuid NULL FK -> document_versions
- contact_id uuid NULL FK -> contacts
- notes text NULL
- created_at timestamptz NOT NULL
```

A check constraint requires at least one evidence target.

## 11. Actions, rankings, and next best action

```text
actions
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- action_type text NOT NULL
- status text NOT NULL
- title text NOT NULL
- rationale text NULL
- due_at timestamptz NULL
- completed_at timestamptz NULL
- expires_at timestamptz NULL
- created_at timestamptz NOT NULL
- updated_at timestamptz NOT NULL
```

Initial action statuses are `proposed`, `ready`, `completed`, `dismissed`, and
`expired`.

```text
action_opportunities
- action_id uuid FK -> actions
- opportunity_id uuid FK -> opportunities
- PRIMARY KEY(action_id, opportunity_id)

action_contacts
- action_id uuid FK -> actions
- contact_id uuid FK -> contacts
- PRIMARY KEY(action_id, contact_id)

action_organizations
- action_id uuid FK -> actions
- organization_id uuid FK -> organizations
- PRIMARY KEY(action_id, organization_id)

action_leads
- action_id uuid FK -> actions
- lead_id uuid FK -> leads
- PRIMARY KEY(action_id, lead_id)
```

### Scoring provenance

```text
scoring_runs
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- model_name text NOT NULL
- model_version text NOT NULL
- started_at timestamptz NOT NULL
- completed_at timestamptz NULL

action_scores
- id uuid PK
- workspace_id uuid NOT NULL FK -> workspaces
- action_id uuid NOT NULL FK -> actions
- scoring_run_id uuid NOT NULL FK -> scoring_runs
- total_score numeric NOT NULL
- score_components jsonb NOT NULL
- scored_at timestamptz NOT NULL
```

### Authoritative selection

```text
next_best_action
- workspace_id uuid PK/FK -> workspaces
- action_id uuid UNIQUE NOT NULL FK -> actions
- selected_at timestamptz NOT NULL
- scoring_run_id uuid NULL FK -> scoring_runs
```

`next_best_action` is the single authoritative pointer. It avoids distributing
an `is_next_best` boolean across candidate rows and makes the one-per-workspace
invariant enforceable by the primary key.

## Relationship summary

```text
Lead --0..1 conversion--> Contact
Lead --0..1 conversion--> Organization
Lead --0..1 conversion--> Opportunity

Contact >--< Organization             through affiliations
Opportunity >--< Organization         through contextual roles
Opportunity >--< Contact              through pursuit roles

Opportunity --< Submission
Opportunity --< Stage History
Opportunity --< Employment Offer      when type = employment
Opportunity --< Contract Agreement    when type = contract
Opportunity --< Interaction
Opportunity --< Document Version
Opportunity --< Qualification Dimension
Opportunity --< Action

Integration Account --< Sync Run
Integration Account --< Source Record >-- canonical CRM records

Workspace --0..1--> Next Best Action
```

## Required integrity constraints

1. A `company` is represented only by `organizations`; no separate `companies`
   aggregate is introduced.
2. A converted lead has exactly one `lead_conversions` row.
3. An opportunity's stage belongs to its pipeline.
4. Employment and contract opportunities use the shared career pipeline.
5. An opportunity has exactly one matching type-detail row.
6. A submission cannot exist without an opportunity.
7. Closed Won employment requires an accepted employment offer.
8. Closed Won contract work requires an executed agreement.
9. Stage-history, score-snapshot, source-record-version, and document-version
   rows are append-only.
10. Submitted artifacts reference immutable document versions.
11. An integration-account deletion cannot cascade-delete organizations,
    contacts, leads, opportunities, interactions, or documents.
12. A workspace has at most one current next-best-action pointer.
13. Workspace identity must match across every relationship. Cross-workspace
    foreign-key associations are rejected.
14. Soft-deleted canonical records remain addressable by audit and provenance
    history.

## Indexing baseline

At minimum, implementation should provide:

- B-tree indexes on every foreign key.
- Partial indexes for non-deleted records on primary list and lookup paths.
- Unique normalized-domain and contact-channel indexes within a workspace.
- `(workspace_id, stage_id, expected_close_date)` on opportunities.
- `(opportunity_id, changed_at DESC)` on stage history.
- `(workspace_id, occurred_at DESC)` on interactions.
- `(integration_account_id, object_type, external_id)` on source records.
- `(source_record_id, observed_at DESC)` on source-record versions.
- `(workspace_id, status, due_at)` on actions.
- `(action_id, scored_at DESC)` on action scores.
- GIN only for bounded JSONB fields with demonstrated query requirements.

## Data-loss and recovery properties

The target schema addresses the organization-loss failure mode through:

- durable canonical organization IDs independent of Dex and LinkedIn IDs;
- immutable source-record observations and typed provenance links;
- restrictive deletion behavior at integration boundaries;
- soft deletion for canonical CRM records;
- append-only lifecycle and scoring histories;
- immutable document versions and content commitments; and
- enough provenance to re-materialize or reconcile records from source systems
  without silently replacing canonical identities.

These properties supplement rather than replace database backup, restore, and
recovery controls.

## Explicit non-goals

- UI navigation, labels, and presentation behavior.
- Exact stage names or probability values.
- ORM class definitions or Alembic migration code.
- Mapping the existing production tables to this target schema.
- Authorizing a production migration, cutover, or deletion of legacy tables.
- Changing the existing command, receipt, SDK, privacy, or content-custody
  architecture.

## Next design artifact

After this schema is reviewed, a separate current-to-target mapping must record:

- every current table and column;
- its target table and column or explicit retirement decision;
- data transforms and deduplication rules;
- organization/company reconciliation rules;
- backfill and referential-integrity ordering;
- backup and rollback requirements;
- validation queries and acceptance thresholds; and
- the explicit cutover and legacy-decommission approval gates.
