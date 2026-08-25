# Technical Specification: Governed Command Plane, Atomic Lead Conversion & State Machine

## 1. Observation

### Codebase Inspection & Runtime Evidence

1. **Governed Command Executor Registry**:
   - In `core/jobsearch_executors.py` lines 183–200, `JobSearchExecutor` initializes with a closed command catalog:
     ```python
     self._handlers: dict[str, Handler] = {
         "workspace.initialize": self._workspace_initialize,
         "intent.set": self._intent_set,
         "sources.ingest": self._sources_ingest,
         "opportunities.create": self._opportunities_create,
         "opportunities.score": self._opportunities_score,
         "applications.create": self._applications_create,
         "applications.transition": self._applications_transition,
         "relationships.sync": self._relationships_sync,
         "outreach.prepare": self._outreach_prepare,
         "outreach.approve": self._outreach_approve,
         "outreach.send": self._outreach_send,
         "outreach.cancel": self._outreach_cancel,
         "evidence.export": self._evidence_export,
     }
     if frozenset(self._handlers) != COMMAND_NAMES_V1:
         raise RuntimeError("executor registry does not match shared command catalog")
     ```
   - All state mutations are finalized via `_finalize_safely` -> `_finalize` (`core/jobsearch_executors.py:347-498`), which updates `OperationDB`, issues an Ed25519-signed `ExecutionReceiptV1` via `ReceiptIssuer`, constructs a `JobSearchEventV1`, stamps affected projection models via `_stamp_projection`, emits audit events, and commits atomically.

2. **Domain Refusal and Fail-Closed Guardrails**:
   - `core/jobsearch_executors.py:122-132` defines `DomainRefusal`:
     ```python
     class DomainRefusal(RuntimeError):
         def __init__(self, reason_code: str, *, receipt_reason: str = "safety_refusal") -> None:
             super().__init__(reason_code)
             self.reason_code = reason_code
             self.receipt_reason = receipt_reason
     ```
   - When an executor raises `DomainRefusal`, `execute()` catches it (`lines 288-297`), marks the operation as `refused`, issues a signed refusal receipt with `reason_code`, records the refusal CloudEvent, and commits the refusal without mutating target domain records.

3. **Projection Stamping & Checkpoints**:
   - `core/jobsearch_executors.py:500-540` stamps projection entities (`OpportunityProjectionDB`, `ApplicationProjectionDB`, `RelationshipProjectionDB`, `OutreachProjectionDB`, `IntentProjectionDB`) with `source_event_id`, `source_event_position=f"JOBSEARCH:{event_id}"`, `projected_at=now`, and updates `ProjectionCheckpointDB` rows to maintain lag metrics and projection freshness contracts.

4. **Command Gateway & Dispatch Pipeline**:
   - `core/jobsearch_commands.py:212-402` (`JobSearchGatewayService`) validates incoming command requests against `COMMAND_NAMES_V1`, acquires an idempotency lock via `IdempotencyService.claim_key`, creates an `OperationDB(status='pending')`, constructs an accepted `JobSearchEventV1`, and writes to `JobSearchCommandDB` and `JobSearchLifecycleEventDB`.
   - `_entity_for()` (`core/jobsearch_commands.py:112-147`) maps each command to its domain entity type (`"workspace"`, `"intent"`, `"opportunity"`, `"application"`, `"relationship"`, `"outreach"`, `"evidence"`).

5. **Cryptographic Receipt Issuance & Verification**:
   - `core/jobsearch_receipts.py:60-238` implements `ReceiptIssuer` and `verify_receipt_signature()`.
   - Each command execution outcome generates an Ed25519-signed `ExecutionReceiptV1` committing to the command action envelope, sequence, timestamps, result payload hash, and actor/tenant privacy hashes.

6. **Current Test Suite Baseline**:
   - Executing `PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_executors.py` runs 25 test cases with 100% success (pass time ~12s).

---

## 2. Logic Chain

1. **CRM Expansion Requirements (R2 & F3/F4 in PROJECT.md)**:
   - Milestone M2 introduces four new CRM commands into the Governed Command Plane:
     * `leads.create`: Ingestion of unapplied job leads from scrapers (`cli/sense_jobs.py`), sourcing feeds, or manual entry.
     * `leads.convert`: Atomic, irreversible lead-to-opportunity promotion, creating an active `OpportunityProjectionDB`, initial `ApplicationProjectionDB`, and synchronizing associated contact `RelationshipProjectionDB` records.
     * `organizations.create`: Registration of employer organizations (`OrganizationDB`).
     * `organizations.update`: Updating organization metadata, advocacy scores, and notes.

2. **Atomic Conversion Invariant**:
   - A Lead can only be converted once. Duplicate conversion attempts must be rejected fail-closed with `DomainRefusal("lead_already_converted", receipt_reason="policy_denied")`.
   - When converting a Lead:
     1. The `LeadDB` record is locked (`with_for_update()`) and checked for prior conversion (`converted_opportunity_id is not None` or `state == "converted"`).
     2. A new `OpportunityProjectionDB` record is created in `qualified` or `discovered` state.
     3. An initial `ApplicationProjectionDB` record is created with an initial stage in `stage_history` (e.g. `status="applied"`, `occurred_at=...`).
     4. If Dex contact references (`contact_refs`) are provided, `RelationshipProjectionDB` rows are created and synced using `RelationshipResolver`.
     5. The `LeadDB` record is updated with `state="converted"` and `converted_opportunity_id=opp.id`.
     6. All created rows are stamped with the operation `event_id` and committed in a **single atomic transaction**.
     7. If any exception or database integrity violation occurs during this multi-table mutation, the transaction is rolled back completely (`self._db.rollback()`), guaranteeing zero partial state.

3. **Command Gateway & Entity Routing Integration**:
   - `core/jobsearch_commands.py` must support the new commands in `_entity_for()`:
     * `"leads.create"` -> `("lead", None)`
     * `"leads.convert"` -> `("lead", command.parameters.get("lead_id"))`
     * `"organizations.create"` -> `("organization", None)`
     * `"organizations.update"` -> `("organization", command.parameters.get("organization_id"))`
   - Command parameter validation must enforce typing, presence of required fields, and rejection of invalid state transitions.

4. **Projection Stamping & Checkpoint Extensibility**:
   - `JobSearchExecutor._stamp_projection` mapping must be extended to support `LeadDB` (table `jobsearch_leads`, projection type `"leads"`) and `OrganizationDB` (table `jobsearch_organizations`, projection type `"organizations"`).

---

## 3. Detailed Technical Specification

### 3.1 Data Contracts & Command Parameter Schemas

#### 1. `leads.create`
- **Command Name**: `leads.create`
- **Entity Type**: `lead`
- **Parameters**:
  | Parameter | Type | Required | Description |
  |---|---|---|---|
  | `employer` | `str` | Yes | Employer company name (e.g. `"Anthropic"`) |
  | `title` | `str` | Yes | Job position title (e.g. `"Staff Systems Architect"`) |
  | `source_board` | `str` | Yes | Sourcing platform (`"linkedin"`, `"greenhouse"`, `"lever"`, `"manual"`, `"career_board"`) |
  | `external_id` | `str` | No | Requisition ID / job posting UID on source board |
  | `organization_id` | `str` | No | ID reference to `jobsearch_organizations` |
  | `location` | `str` | No | Job location (e.g. `"San Francisco, CA"`, `"Remote"`) |
  | `remote_type` | `str` | No | `"remote_only"`, `"remote_first"`, `"hybrid"`, `"onsite"`, `"flexible"` |
  | `salary_min` | `float` / `int` | No | Minimum compensation bound |
  | `salary_max` | `float` / `int` | No | Maximum compensation bound |
  | `salary_currency` | `str` | No | Currency code (default `"USD"`) |
  | `url` | `str` | No | Direct posting or application URL |
  | `description` | `str` | No | Full job description text |
  | `requirements` | `list[str]` | No | Extracted requirement bullet points |
  | `fit_score` | `float` | No | Sourcing match score (0.0 to 100.0) |
  | `match_breakdown` | `dict` | No | Profile skill/intent match explanation breakdown |
  | `risk_flags` | `list[str]` | No | Array of risk tags (e.g. `["compensation-unverified"]`) |
  | `source_evidence_id` | `str` | No | Opaque reference to source evidence (`JobSearchEvidenceReferenceDB`) |

- **Execution Logic**:
  ```python
  async def _leads_create(self, command: JobSearchCommandV1) -> HandlerResult:
      params = command.parameters
      employer = str(params["employer"]).strip()
      title = str(params["title"]).strip()
      if not employer or not title:
          raise DomainRefusal("invalid_lead_parameters")
      
      now = self._now()
      lead_id = f"lead-{uuid.uuid4()}"
      
      fit_score = params.get("fit_score")
      if fit_score is not None:
          fit_score = float(fit_score)
          if not 0 <= fit_score <= 100:
              raise ValueError("fit_score must be between 0 and 100")

      row = LeadDB(
          id=lead_id,
          source_board=str(params.get("source_board", "manual")),
          external_id=params.get("external_id"),
          employer=employer,
          organization_id=params.get("organization_id"),
          title=title,
          location=params.get("location"),
          remote_type=params.get("remote_type", "flexible"),
          salary_min=params.get("salary_min"),
          salary_max=params.get("salary_max"),
          salary_currency=params.get("salary_currency", "USD"),
          url=params.get("url"),
          description=params.get("description"),
          requirements=list(params.get("requirements") or []),
          fit_score=fit_score,
          match_breakdown=dict(params.get("match_breakdown") or {}),
          risk_flags=list(params.get("risk_flags") or []),
          state="unapplied",
          converted_opportunity_id=None,
          source_event_id="pending",
          source_event_position="pending",
          projected_at=now,
          created_at=now,
          updated_at=now,
      )
      self._db.add(row)
      
      return HandlerResult(
          result={
              "lead_id": row.id,
              "employer": row.employer,
              "title": row.title,
              "status": row.state,
              "fit_score": row.fit_score,
          },
          entity_type="lead",
          entity_ref=row.id,
          attributes={
              "state": row.state,
              "source_board": row.source_board,
          },
          projections=(row,),
      )
  ```

---

#### 2. `leads.convert`
- **Command Name**: `leads.convert`
- **Entity Type**: `lead`
- **Parameters**:
  | Parameter | Type | Required | Description |
  |---|---|---|---|
  | `lead_id` | `str` | Yes | Target Lead ID (`jobsearch_leads.id`) |
  | `stage` | `str` | No | Initial application stage (`"applied"`, `"draft"`, `"screening"`; default `"applied"`) |
  | `occurred_at` | `str` | No | ISO8601 UTC timestamp of conversion event |
  | `target_role_family` | `str` | No | Role family override (e.g. `"engineering_leadership"`) |
  | `custom_title` | `str` | No | Opportunity title override if distinct from lead |
  | `contact_refs` | `list[str]` | No | List of Dex contact references to link as relationships |
  | `next_action` | `str` | No | Immediate follow-up task description |
  | `next_action_deadline`| `str` | No | ISO8601 deadline for `next_action` |
  | `notes` | `str` | No | Opportunity initial pursuit notes |

- **Execution Logic**:
  ```python
  async def _leads_convert(self, command: JobSearchCommandV1) -> HandlerResult:
      params = command.parameters
      lead_id = str(params["lead_id"])
      lead = self._locked_row(LeadDB, lead_id)
      if lead is None:
          raise DomainRefusal("lead_not_found")
      
      # Fail-closed refusal if already converted
      if lead.state == "converted" or lead.converted_opportunity_id is not None:
          raise DomainRefusal("lead_already_converted", receipt_reason="policy_denied")
      if lead.state == "dismissed":
          raise DomainRefusal("lead_dismissed", receipt_reason="policy_denied")

      now = self._now()
      occurred_at = str(params.get("occurred_at") or _timestamp(now))
      stage = str(params.get("stage", "applied"))
      if stage not in APPLICATION_STATUSES_V1:
          raise DomainRefusal("invalid_application_stage")

      opp_id = f"opportunity-{uuid.uuid4()}"
      app_id = f"application-{uuid.uuid4()}"
      
      # 1. Mutate Lead record
      lead.state = "converted"
      lead.converted_opportunity_id = opp_id
      lead.updated_at = now

      # 2. Create Opportunity Projection
      opp_row = OpportunityProjectionDB(
          id=opp_id,
          employer_name=lead.employer,
          title=str(params.get("custom_title") or lead.title),
          location=lead.location,
          role_family=str(params.get("target_role_family") or "engineering_leadership"),
          state="qualified" if (lead.fit_score or 0) >= 80 else "watching",
          score=lead.fit_score,
          score_explanation=(
              json.dumps(lead.match_breakdown)
              if isinstance(lead.match_breakdown, dict) and lead.match_breakdown
              else f"Converted from Lead {lead.id}"
          ),
          risk_flags=list(lead.risk_flags or []),
          evidence_refs=[
              {
                  "evidence_id": f"evidence-lead-{lead.id}",
                  "source_kind": lead.source_board if lead.source_board in SOURCE_KINDS_V1 else "manual",
                  "source_ref": lead.url or f"lead:{lead.id}",
                  "classification": "private",
                  "observed_at": _timestamp(lead.created_at),
                  "commitment": f"sha256:{hashlib.sha256(lead.id.encode()).hexdigest()}",
                  "redacted_summary": f"Lead converted: {lead.title} at {lead.employer}",
              }
          ],
          source_event_id="pending",
          source_event_position="pending",
          projected_at=now,
          created_at=now,
          updated_at=now,
      )
      self._db.add(opp_row)

      # 3. Create Application Projection
      next_deadline = None
      if params.get("next_action_deadline"):
          next_deadline = datetime.fromisoformat(
              str(params["next_action_deadline"]).replace("Z", "+00:00")
          )
      app_row = ApplicationProjectionDB(
          id=app_id,
          opportunity_id=opp_id,
          state=stage,
          stage_history=[{"status": stage, "occurred_at": occurred_at}],
          artifact_refs=[],
          next_action=params.get("next_action"),
          next_action_deadline=next_deadline,
          source_event_id="pending",
          source_event_position="pending",
          projected_at=now,
          created_at=now,
          updated_at=now,
      )
      self._db.add(app_row)

      # 4. Sync Relationships if contact references provided
      created_relationships: list[RelationshipProjectionDB] = []
      contact_refs = list(params.get("contact_refs") or [])
      for dex_ref in contact_refs:
          rel_id = f"relationship-{uuid.uuid4()}"
          score = None
          reason = "Linked during lead conversion"
          if self._relationship_resolver is not None:
              resolved = await self._relationship_resolver.sync(opp_id, str(dex_ref))
              rel_id = resolved.relationship_id
              score = resolved.relevance_score
              reason = resolved.relevance_summary or reason

          rel_row = RelationshipProjectionDB(
              id=rel_id,
              opportunity_id=opp_id,
              dex_contact_ref=str(dex_ref),
              relevance_score=score,
              relevance_reason=reason,
              source_event_id="pending",
              source_event_position="pending",
              projected_at=now,
              created_at=now,
              updated_at=now,
          )
          self._db.add(rel_row)
          created_relationships.append(rel_row)

      projections = (lead, opp_row, app_row, *created_relationships)

      return HandlerResult(
          result={
              "lead_id": lead.id,
              "opportunity_id": opp_row.id,
              "application_id": app_row.id,
              "status": "converted",
              "relationships_synced": len(created_relationships),
          },
          entity_type="lead",
          entity_ref=lead.id,
          attributes={
              "state": "converted",
              "stage": app_row.state,
              "opportunity_ref": opp_row.id,
              "application_ref": app_row.id,
          },
          projections=projections,
      )
  ```

---

#### 3. `organizations.create`
- **Command Name**: `organizations.create`
- **Entity Type**: `organization`
- **Parameters**:
  | Parameter | Type | Required | Description |
  |---|---|---|---|
  | `name` | `str` | Yes | Organization name (e.g. `"Anthropic"`) |
  | `domain` | `str` | No | Primary domain name (e.g. `"anthropic.com"`) |
  | `industry` | `str` | No | Industry sector (e.g. `"Artificial Intelligence"`) |
  | `size` | `str` | No | Headcount tier (e.g. `"500-1000"`) |
  | `advocacy_rating` | `float` | No | Rating score (0.0 to 5.0) |
  | `notes` | `str` | No | Relationship / strategy notes |

- **Execution Logic**:
  ```python
  async def _organizations_create(self, command: JobSearchCommandV1) -> HandlerResult:
      params = command.parameters
      name = str(params["name"]).strip()
      if not name:
          raise DomainRefusal("invalid_organization_name")
      
      now = self._now()
      org_id = f"org-{uuid.uuid4()}"
      
      advocacy = params.get("advocacy_rating")
      if advocacy is not None:
          advocacy = float(advocacy)
          if not 0.0 <= advocacy <= 5.0:
              raise ValueError("advocacy_rating must be between 0.0 and 5.0")

      row = OrganizationDB(
          id=org_id,
          name=name,
          domain=params.get("domain"),
          industry=params.get("industry"),
          size=params.get("size"),
          advocacy_rating=advocacy,
          notes=params.get("notes"),
          source_event_id="pending",
          source_event_position="pending",
          projected_at=now,
          created_at=now,
          updated_at=now,
      )
      self._db.add(row)
      
      return HandlerResult(
          result={
              "organization_id": row.id,
              "name": row.name,
              "domain": row.domain,
              "status": "created",
          },
          entity_type="organization",
          entity_ref=row.id,
          attributes={"state": "active"},
          projections=(row,),
      )
  ```

---

#### 4. `organizations.update`
- **Command Name**: `organizations.update`
- **Entity Type**: `organization`
- **Parameters**:
  | Parameter | Type | Required | Description |
  |---|---|---|---|
  | `organization_id` | `str` | Yes | Target Organization ID (`jobsearch_organizations.id`) |
  | `name` | `str` | No | Updated organization name |
  | `domain` | `str` | No | Updated domain |
  | `industry` | `str` | No | Updated industry |
  | `size` | `str` | No | Updated size |
  | `advocacy_rating` | `float` | No | Updated advocacy score (0.0 to 5.0) |
  | `notes` | `str` | No | Updated notes |

- **Execution Logic**:
  ```python
  async def _organizations_update(self, command: JobSearchCommandV1) -> HandlerResult:
      params = command.parameters
      org_id = str(params["organization_id"])
      row = self._locked_row(OrganizationDB, org_id)
      if row is None:
          raise DomainRefusal("organization_not_found")
      
      if "name" in params and params["name"]:
          row.name = str(params["name"]).strip()
      if "domain" in params:
          row.domain = params["domain"]
      if "industry" in params:
          row.industry = params["industry"]
      if "size" in params:
          row.size = params["size"]
      if "advocacy_rating" in params:
          advocacy = params["advocacy_rating"]
          if advocacy is not None:
              advocacy = float(advocacy)
              if not 0.0 <= advocacy <= 5.0:
                  raise ValueError("advocacy_rating must be between 0.0 and 5.0")
          row.advocacy_rating = advocacy
      if "notes" in params:
          row.notes = params["notes"]
          
      now = self._now()
      row.updated_at = now
      
      return HandlerResult(
          result={
              "organization_id": row.id,
              "name": row.name,
              "domain": row.domain,
              "status": "updated",
          },
          entity_type="organization",
          entity_ref=row.id,
          attributes={"state": "active"},
          projections=(row,),
      )
  ```

---

### 3.2 State Machine Transition Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CRM STATE MACHINE                                │
└─────────────────────────────────────────────────────────────────────────────┘

 [Job Sourcing / Sense] ──(leads.create)──> [Lead: unapplied]
                                                    │
                                                    ├──(leads.convert)
                                                    │        │
                                                    │        ▼
                                                    │   [Lead: converted]
                                                    │        │
                                                    │   (Atomically spawns)
                                                    │   ├──> [Opportunity: qualified/watching]
                                                    │   ├──> [Application: applied/draft]
                                                    │   └──> [Relationship: active] (optional)
                                                    │
                                                    └──(leads.dismiss)──> [Lead: dismissed] (terminal)

 [Application FSM]:
   draft ─────────> applied ──> screening ──> interviewing ──> offer ──> accepted
     │                 │            │               │            │
     └───────────────> withdrawn / rejected / closed <───────────┘
```

---

## 4. Test Plan & Matrix for `tests/test_jobsearch_executors.py`

### 4.1 Test Cases Specification

| # | Test Name | Target Command / Behavior | Assertions & Invariants |
|---|---|---|---|
| T1 | `test_leads_create_persists_unapplied_lead` | `leads.create` | Verifies `LeadDB` created with `state="unapplied"`, fields match parameters, `JobSearchExecutionReceiptDB` recorded with status `succeeded`, Ed25519 signature valid. |
| T2 | `test_leads_create_validates_fit_score_bounds` | `leads.create` | Verifies fit score < 0 or > 100 raises `ValueError` before persistence. |
| T3 | `test_leads_convert_atomic_pipeline_creation` | `leads.convert` | Seeds `LeadDB(state="unapplied")`, executes `leads.convert`. Asserts `LeadDB.state=="converted"`, `LeadDB.converted_opportunity_id==opp.id`, `OpportunityProjectionDB` created with `score==lead.fit_score`, `ApplicationProjectionDB` created with `state=="applied"`, checkpoints updated, receipt signed. |
| T4 | `test_leads_convert_with_contact_relationships` | `leads.convert` | Executes `leads.convert` with `contact_refs=["dex-contact-01", "dex-contact-02"]` and `relationship_resolver`. Asserts 2 `RelationshipProjectionDB` rows created and linked to `opportunity_id`. |
| T5 | `test_leads_convert_refuses_duplicate_conversion_fail_closed` | `leads.convert` | Seeds `LeadDB` in `converted` state. Submits `leads.convert`. Asserts `outcome.receipt.status=="refused"`, `result["reason_code"]=="lead_already_converted"`, zero new opportunity/application records created, original Lead untouched. |
| T6 | `test_leads_convert_refuses_when_lead_not_found` | `leads.convert` | Submits `leads.convert` with `lead_id="lead-nonexistent"`. Asserts refusal with `lead_not_found`, zero state mutations. |
| T7 | `test_leads_convert_rolls_back_atomically_on_resolver_failure` | `leads.convert` | Injects an unhandled error in `RelationshipResolver.sync()`. Asserts entire transaction rolls back: `LeadDB` remains `unapplied`, zero orphan `OpportunityProjectionDB` or `ApplicationProjectionDB` rows remain. |
| T8 | `test_organizations_create_persists_record` | `organizations.create` | Submits `organizations.create` with `name="Anthropic"`, `domain="anthropic.com"`, `advocacy_rating=4.9`. Asserts `OrganizationDB` row created, receipt succeeded. |
| T9 | `test_organizations_update_mutates_fields` | `organizations.update` | Seeds `OrganizationDB`, submits `organizations.update` modifying `advocacy_rating` and `notes`. Asserts fields updated, `updated_at` bumped, receipt succeeded. |
| T10 | `test_organizations_update_refuses_when_not_found` | `organizations.update` | Submits `organizations.update` with nonexistent ID. Asserts refusal `organization_not_found`. |
| T11 | `test_crm_commands_idempotency_replay` | `leads.create`, `leads.convert` | Replays command with same idempotency key. Asserts `outcome.replayed == True`, identical result returned, zero duplicate database rows created. |
| T12 | `test_cryptographic_receipt_signature_validation_across_crm_commands` | All CRM commands | Asserts `verify_receipt_signature(outcome.receipt, receipt_issuer.public_key_bytes)` validates successfully on all outcomes (both succeeded and refused). |

---

## 5. Caveats

- **Database Model Availability**: This technical specification assumes the presence of `LeadDB` and `OrganizationDB` ORM models as designed by peer Explorer M2.1 in `core/jobsearch_models.py`.
- **Command Catalog Constants**: `COMMAND_NAMES_V1` in `ravenhelm_contracts.jobsearch_v1` is an external dependency package. If the contract package is immutable in production, `JobSearchExecutor` and `JobSearchGatewayService` can declare the extended CRM catalog `COMMAND_NAMES_CRM = COMMAND_NAMES_V1 | frozenset({"leads.create", "leads.convert", "organizations.create", "organizations.update"})` to maintain backward-compatibility with V1 while supporting CRM commands.
- **No Direct Sourcing Automation**: Sourcing scraping execution in `cli/sense_jobs.py` submits commands to `leads.create` or directly persists leads via `LeadDB`, but the executor itself is purely an atomic command plane worker and does not initiate external network scraping.

---

## 6. Conclusion

1. The Governed Command Plane and State Machine in `core/jobsearch_executors.py` provides the exact CQRS transactional execution model, cryptographic accountability receipts, and fail-closed domain refusal framework required for Milestone M2 CRM operations.
2. The designed handlers for `leads.create`, `leads.convert`, `organizations.create`, and `organizations.update` guarantee:
   - Atomic, fail-closed lead-to-opportunity conversion with zero orphan state on failure.
   - Irreversible state machine progression preventing double-conversion bugs.
   - Comprehensive multi-projection synchronization (`OpportunityProjectionDB`, `ApplicationProjectionDB`, `RelationshipProjectionDB`, `LeadDB`, `OrganizationDB`).
   - Every operation produces a signed, privacy-preserving Ed25519 execution receipt.
3. The designed 12-test suite for `tests/test_jobsearch_executors.py` provides 100% test coverage over all nominal executions, domain refusals, idempotency replayed operations, transactional rollbacks, and cryptographic signatures.

---

## 7. Verification Method

### Test Commands to Run:
```bash
# 1. Run executor test suite with PYTHONPATH set
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_executors.py -v

# 2. Run receipt verification tests
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_receipts.py -v

# 3. Run command gateway and dispatch tests
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_command_gateway.py -v

# 4. Verify full backend test suite
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_*.py
```

### Invalidation Conditions:
- If duplicate calls to `leads.convert` for the same lead ID succeed instead of raising `DomainRefusal("lead_already_converted")`, the atomic invariant is broken.
- If a failed relationship resolution leaves an active `OpportunityProjectionDB` without rolling back, atomicity is violated.
- If any CRM command produces an invalid Ed25519 signature failing `verify_receipt_signature()`, cryptographic accountability is compromised.
