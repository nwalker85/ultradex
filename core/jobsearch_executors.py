"""Closed executor registry for governed job-search commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Awaitable, Callable, Protocol
import uuid

from ravenhelm_contracts import (
    JobSearchCommandV1,
    JobSearchEventV1,
    JobSearchEvidenceReferenceV1,
)
from ravenhelm_contracts.accountability_v1 import (
    ExecutionReceiptV1,
    hash_execution_receipt_v1,
)
from ravenhelm_contracts.jobsearch_v1 import (
    APPLICATION_STATUSES_V1,
    COMMAND_NAMES_V1,
    OUTREACH_CANCEL_ALLOWED_SOURCE_STATUSES_V1,
    OUTREACH_CANCEL_TARGET_STATUS_V1,
    SOURCE_KINDS_V1,
)
from sqlalchemy.orm import Session

from .event_producer import EventProducer
from .jobsearch_commands import COMMAND_NAMES_CRM, build_jobsearch_event
from .jobsearch_models import (
    INTENT_SINGLETON_ID,
    WORKSPACE_SINGLETON_ID,
    ApplicationProjectionDB,
    IntentProjectionDB,
    JobSearchApprovalDB,
    JobSearchCommandDB,
    JobSearchEvidenceReferenceDB,
    JobSearchExecutionReceiptDB,
    JobSearchLifecycleEventDB,
    LeadDB,
    OpportunityProjectionDB,
    OrganizationDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)
from .jobsearch_receipts import ReceiptIssuer
from .models import EventType, OperationDB, OperationStatus
from .operation_service import OperationService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # Job-search rows are written in UTC; SQLite drops the timezone marker.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _timestamp(value: datetime) -> str:
    return _aware(value).astimezone(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


@dataclass(frozen=True)
class EvidenceIngestResult:
    evidence_id: str
    source_kind: str
    source_ref: str
    observed_at: str
    commitment: str
    redacted_summary: str


@dataclass(frozen=True)
class OpportunityScoreResult:
    score: int | float
    explanation: str
    risk_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipSyncResult:
    relationship_id: str
    relevance_score: int | float | None = None
    relevance_summary: str | None = None


class SourceAdapter(Protocol):
    async def ingest(
        self,
        command: JobSearchCommandV1,
    ) -> EvidenceIngestResult: ...


class OpportunityScorer(Protocol):
    async def score(
        self,
        opportunity_id: str,
        lens: str,
    ) -> OpportunityScoreResult: ...


class RelationshipResolver(Protocol):
    async def sync(
        self,
        opportunity_id: str,
        dex_contact_ref: str,
    ) -> RelationshipSyncResult: ...


class OutreachSender(Protocol):
    async def send(
        self,
        *,
        outreach_id: str,
        channel: str,
        message_commitment: str,
        idempotency_key: str,
    ) -> str: ...


class DomainRefusal(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        *,
        receipt_reason: str = "safety_refusal",
    ) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.receipt_reason = receipt_reason


class RetryableCommandError(RuntimeError):
    """An executor failure that may be retried within the task budget."""


@dataclass(frozen=True)
class HandlerResult:
    result: dict[str, object]
    entity_type: str
    entity_ref: str
    attributes: dict[str, object]
    projections: tuple[object, ...] = ()


@dataclass(frozen=True)
class JobSearchExecutionOutcome:
    event: JobSearchEventV1
    receipt: ExecutionReceiptV1
    result: dict[str, object]
    replayed: bool = False


Handler = Callable[[JobSearchCommandV1], Awaitable[HandlerResult]]


class JobSearchExecutor:
    """Validate, dispatch, and atomically terminalize one canonical task."""

    def __init__(
        self,
        db: Session,
        receipt_issuer: ReceiptIssuer,
        *,
        source_adapter: SourceAdapter | None = None,
        scorer: OpportunityScorer | None = None,
        relationship_resolver: RelationshipResolver | None = None,
        sender: OutreachSender | None = None,
        now: Callable[[], datetime] = _utcnow,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._db = db
        self._receipt_issuer = receipt_issuer
        self._source_adapter = source_adapter
        self._scorer = scorer
        self._relationship_resolver = relationship_resolver
        self._sender = sender
        self._now = now
        self._max_attempts = max_attempts
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
            "leads.create": self._leads_create,
            "leads.convert": self._leads_convert,
            "organizations.create": self._organizations_create,
            "organizations.update": self._organizations_update,
        }
        if frozenset(self._handlers) != COMMAND_NAMES_CRM:
            raise RuntimeError("executor registry does not match shared command catalog")

    @property
    def command_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def _locked_row(self, model, row_id: str):
        primary_key = model.__mapper__.primary_key[0]
        return (
            self._db.query(model)
            .filter(primary_key == row_id)
            .populate_existing()
            .with_for_update()
            .one_or_none()
        )

    def _existing_outcome(
        self,
        command: JobSearchCommandV1,
    ) -> JobSearchExecutionOutcome | None:
        existing = (
            self._db.query(JobSearchExecutionReceiptDB)
            .filter_by(operation_id=command.context.operation_id)
            .one_or_none()
        )
        if existing is None:
            return None
        event_row = self._db.get(
            JobSearchLifecycleEventDB,
            existing.event_id,
        )
        if event_row is None:
            raise RuntimeError("terminal receipt has no lifecycle event")
        operation = self._db.get(
            OperationDB,
            command.context.operation_id,
        )
        if operation is None:
            raise RuntimeError("terminal receipt has no operation")
        return JobSearchExecutionOutcome(
            event=JobSearchEventV1.from_dict(event_row.payload),
            receipt=ExecutionReceiptV1.from_dict(existing.payload),
            result=dict(operation.result or {}),
            replayed=True,
        )

    async def execute(
        self,
        value: JobSearchCommandV1 | dict[str, object],
        *,
        attempt: int = 1,
    ) -> JobSearchExecutionOutcome:
        command = (
            value
            if isinstance(value, JobSearchCommandV1)
            else JobSearchCommandV1.from_dict(value)
        )
        accepted = self._db.get(
            JobSearchCommandDB,
            command.context.operation_id,
        )
        if accepted is None or accepted.command_id != command.command_id:
            raise ValueError("task has no matching durable accepted command")

        operation = self._locked_row(
            OperationDB,
            command.context.operation_id,
        )
        if operation is None:
            raise ValueError("task operation does not exist")
        existing = self._existing_outcome(command)
        if existing is not None:
            return existing
        if operation.status == OperationStatus.PENDING:
            OperationService.start_operation(
                self._db,
                operation.id,
                commit=False,
            )
            EventProducer.emit(
                self._db,
                EventType.TASK_STARTED,
                operation.id,
                {"task": command.command},
                commit=False,
            )

        try:
            result = await self._handlers[command.command](command)
        except DomainRefusal as refusal:
            return self._finalize_safely(
                command,
                status="refused",
                receipt_reason=refusal.receipt_reason,
                result={
                    "status": "refused",
                    "reason_code": refusal.reason_code,
                },
            )
        except RetryableCommandError:
            self._db.rollback()
            if attempt < self._max_attempts:
                EventProducer.emit(
                    self._db,
                    "task.retrying",
                    command.context.operation_id,
                    {
                        "attempt": attempt,
                        "max_attempts": self._max_attempts,
                    },
                )
                raise
            return self._finalize_safely(
                command,
                status="failed",
                receipt_reason="executor_failure",
                result={
                    "status": "failed",
                    "reason_code": "retry_budget_exhausted",
                },
            )
        except Exception:
            self._db.rollback()
            return self._finalize_safely(
                command,
                status="failed",
                receipt_reason="executor_failure",
                result={
                    "status": "failed",
                    "reason_code": "executor_failure",
                },
            )

        return self._finalize_safely(
            command,
            status="succeeded",
            receipt_reason=None,
            result=result.result,
            handler_result=result,
        )

    def mark_event_published(self, event_id: str) -> None:
        row = self._db.get(JobSearchLifecycleEventDB, event_id)
        if row is None:
            raise ValueError("lifecycle event does not exist")
        row.published_at = self._now()
        self._db.commit()

    def _finalize_safely(
        self,
        command: JobSearchCommandV1,
        **kwargs: object,
    ) -> JobSearchExecutionOutcome:
        try:
            return self._finalize(command, **kwargs)
        except Exception:
            self._db.rollback()
            raise

    def _finalize(
        self,
        command: JobSearchCommandV1,
        *,
        status: str,
        receipt_reason: str | None,
        result: dict[str, object],
        handler_result: HandlerResult | None = None,
    ) -> JobSearchExecutionOutcome:
        now = self._now()
        operation = self._locked_row(
            OperationDB,
            command.context.operation_id,
        )
        if operation is None:  # pragma: no cover - checked before execution
            raise RuntimeError("operation disappeared during execution")
        existing = self._existing_outcome(command)
        if existing is not None:
            return existing
        if status == "succeeded":
            operation = OperationService.complete_operation(
                self._db,
                operation.id,
                result,
                commit=False,
            )
            lifecycle_state = "succeeded"
            metric_result = "success"
            legacy_event = EventType.TASK_COMPLETED
        elif status == "refused":
            operation = OperationService.refuse_operation(
                self._db,
                operation.id,
                result["reason_code"],
                commit=False,
            )
            operation.result = result
            lifecycle_state = "refused"
            metric_result = "refused"
            legacy_event = "task.refused"
        else:
            operation = OperationService.fail_operation(
                self._db,
                operation.id,
                result["reason_code"],
                commit=False,
            )
            operation.result = result
            lifecycle_state = "failed"
            metric_result = "failure"
            legacy_event = EventType.TASK_FAILED

        event_id = self._receipt_issuer.new_opaque_id()
        receipt = self._receipt_issuer.issue(
            command=command,
            event_id=event_id,
            sequence=1,
            status=status,  # type: ignore[arg-type]
            started_at=operation.started_at or operation.created_at,
            completed_at=now,
            result=result if status == "succeeded" else None,
            reason_code=receipt_reason,
        )
        event = build_jobsearch_event(
            command=command,
            operation=operation,
            event_id=event_id,
            domain_event_type=(
                f"jobsearch.{command.command}.{lifecycle_state}.v1"
            ),
            lifecycle_state=lifecycle_state,
            result=metric_result,
            occurred_at=now,
            entity_type=(
                None if handler_result is None else handler_result.entity_type
            ),
            entity_ref=(
                None if handler_result is None else handler_result.entity_ref
            ),
            receipt_id=receipt.receipt_id,
            attributes=(
                None if handler_result is None else handler_result.attributes
            ),
            refusal_code=(
                str(result["reason_code"])
                if lifecycle_state == "refused"
                else None
            ),
            refusal_reason=(
                "Job-search command refused"
                if lifecycle_state == "refused"
                else None
            ),
        )
        for projection in (
            () if handler_result is None else handler_result.projections
        ):
            self._stamp_projection(projection, event_id, now)
        EventProducer.emit(
            self._db,
            legacy_event,
            operation.id,
            {
                "result": metric_result,
                **(
                    {"reason_code": result["reason_code"]}
                    if "reason_code" in result
                    else {}
                ),
            },
            commit=False,
        )
        self._db.add_all(
            [
                JobSearchLifecycleEventDB(
                    event_id=event_id,
                    operation_id=operation.id,
                    event_type=event.domain_event_type,
                    payload=event.to_dict(),
                    occurred_at=now,
                    published_at=None,
                ),
                JobSearchExecutionReceiptDB(
                    receipt_id=receipt.receipt_id,
                    operation_id=operation.id,
                    event_id=event_id,
                    status=receipt.status,
                    reason_code=receipt.reason_code,
                    payload=receipt.to_dict(),
                    receipt_hash=hash_execution_receipt_v1(receipt),
                    created_at=now,
                    completed_at=now,
                ),
            ]
        )
        self._db.commit()
        return JobSearchExecutionOutcome(
            event=event,
            receipt=receipt,
            result=result,
        )

    def _stamp_projection(
        self,
        projection: object,
        event_id: str,
        now: datetime,
    ) -> None:
        mapping = {
            OpportunityProjectionDB: "opportunities",
            ApplicationProjectionDB: "applications",
            RelationshipProjectionDB: "relationships",
            OutreachProjectionDB: "outreach",
            IntentProjectionDB: "intent",
            OrganizationDB: "organizations",
            LeadDB: "leads",
        }
        projection_type = mapping.get(type(projection))
        if projection_type is None:
            raise TypeError("handler returned an unsupported projection row")
        projection.source_event_id = event_id
        projection.source_event_position = f"JOBSEARCH:{event_id}"
        projection.projected_at = now
        projection.updated_at = now
        checkpoint = self._db.get(
            ProjectionCheckpointDB,
            projection_type,
        )
        if checkpoint is None:
            checkpoint = ProjectionCheckpointDB(
                projection_type=projection_type,
                source_event_id=event_id,
                source_event_position=f"JOBSEARCH:{event_id}",
                projected_at=now,
                lag_ms=0,
                status="fresh",
            )
            self._db.add(checkpoint)
        else:
            checkpoint.source_event_id = event_id
            checkpoint.source_event_position = f"JOBSEARCH:{event_id}"
            checkpoint.projected_at = now
            checkpoint.lag_ms = 0
            checkpoint.status = "fresh"

    async def _workspace_initialize(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        # Zero-parameter, idempotent: it always resolves to the same private
        # workspace identity. No projection table exists for "workspace" in
        # JOBSEARCH_PROJECTION_TYPES_V1, so there is nothing to stamp; this
        # command only ever produces its lifecycle event and receipt.
        return HandlerResult(
            result={
                "workspace_id": WORKSPACE_SINGLETON_ID,
                "status": "initialized",
            },
            entity_type="workspace",
            entity_ref=WORKSPACE_SINGLETON_ID,
            # JobSearchEventAttributesV1 is closed (additionalProperties:
            # false) over a fixed key set that has no "workspace status"
            # concept — the op result above already carries that. Only
            # `result` (auto-injected by _finalize) belongs here.
            attributes={},
        )

    async def _intent_set(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        params = command.parameters
        now = self._now()
        row = self._locked_row(IntentProjectionDB, INTENT_SINGLETON_ID)
        is_new = row is None
        if row is None:
            row = IntentProjectionDB(
                id=INTENT_SINGLETON_ID,
                source_event_id="pending",
                source_event_position="pending",
                projected_at=now,
                created_at=now,
                updated_at=now,
            )
        row.target_role_families = list(params["target_role_families"])
        row.target_domains = list(params["target_domains"])
        row.seniority_band = str(params["seniority_band"])
        row.location_preference = params.get("location_preference")
        row.remote_preference = str(params["remote_preference"])
        row.employer_exclusions = list(params["employer_exclusions"])
        row.weights = dict(params["weights"])
        row.narrative = params.get("narrative")
        if is_new:
            self._db.add(row)

        # Replace-style singleton write: rescore every existing opportunity
        # against the new targeting record in the same atomic operation, so
        # the projection never shows opportunities scored against a stale
        # Intent. Best-effort: if no scorer is bound, the Intent still sets
        # successfully and opportunities keep whatever score they had.
        projections: list[object] = [row]
        rescored_count = 0
        if self._scorer is not None:
            opportunities = (
                self._db.query(OpportunityProjectionDB)
                .order_by(OpportunityProjectionDB.id.asc())
                .all()
            )
            for opportunity in opportunities:
                scored = await self._scorer.score(
                    opportunity.id,
                    "default",
                )
                if not 0 <= scored.score <= 100:
                    raise ValueError("score must be between 0 and 100")
                if len(scored.explanation) > 1000:
                    raise ValueError(
                        "score explanation exceeds contract maximum"
                    )
                opportunity.score = scored.score
                opportunity.score_explanation = scored.explanation
                opportunity.risk_flags = list(scored.risk_flags)
                opportunity.state = (
                    "qualified" if scored.score >= 80 else "watching"
                )
                projections.append(opportunity)
                rescored_count += 1

        return HandlerResult(
            result={
                "intent_id": row.id,
                "rescored_count": rescored_count,
            },
            entity_type="intent",
            entity_ref=row.id,
            # JobSearchEventAttributesV1 is closed over a fixed key set with
            # no "rescored_count" concept — that lives in the op result above.
            attributes={},
            projections=tuple(projections),
        )

    async def _sources_ingest(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        if self._source_adapter is None:
            raise DomainRefusal("source_adapter_unbound")
        result = await self._source_adapter.ingest(command)
        contract = JobSearchEvidenceReferenceV1.from_dict(
            {
                "evidence_id": result.evidence_id,
                "source_kind": result.source_kind,
                "source_ref": result.source_ref,
                "classification": "private",
                "observed_at": result.observed_at,
                "commitment": result.commitment,
                "redacted_summary": result.redacted_summary,
            }
        )
        if (
            contract.source_kind != command.parameters["source_kind"]
            or contract.source_ref != command.parameters["source_ref"]
            or contract.observed_at != command.parameters["observed_at"]
        ):
            raise DomainRefusal("source_result_mismatch")
        existing = self._db.get(JobSearchEvidenceReferenceDB, contract.evidence_id)
        if existing is not None:
            if existing.commitment != contract.commitment:
                raise DomainRefusal("evidence_commitment_conflict")
            return HandlerResult(
                result={"evidence_id": existing.evidence_id},
                entity_type="evidence",
                entity_ref=existing.evidence_id,
                attributes={
                    "connector": existing.source_kind,
                    "evidence_ref": existing.evidence_id,
                    "commitment": existing.commitment,
                },
            )
        observed = datetime.fromisoformat(
            contract.observed_at.replace("Z", "+00:00")
        )
        self._db.add(
            JobSearchEvidenceReferenceDB(
                evidence_id=contract.evidence_id,
                source_kind=contract.source_kind,
                source_ref=contract.source_ref,
                classification=contract.classification,
                observed_at=observed,
                commitment=contract.commitment,
                redacted_summary=contract.redacted_summary,
                created_at=self._now(),
            )
        )
        return HandlerResult(
            result={"evidence_id": contract.evidence_id},
            entity_type="evidence",
            entity_ref=contract.evidence_id,
            attributes={
                "connector": contract.source_kind,
                "evidence_ref": contract.evidence_id,
                "commitment": contract.commitment,
            },
        )

    async def _opportunities_create(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        evidence_id = str(command.parameters["source_evidence_id"])
        evidence = self._db.get(JobSearchEvidenceReferenceDB, evidence_id)
        if evidence is None:
            raise DomainRefusal("source_evidence_not_found")
        evidence_contract = JobSearchEvidenceReferenceV1.from_dict(
            {
                "evidence_id": evidence.evidence_id,
                "source_kind": evidence.source_kind,
                "source_ref": evidence.source_ref,
                "classification": evidence.classification,
                "observed_at": _timestamp(evidence.observed_at),
                "commitment": evidence.commitment,
                "redacted_summary": evidence.redacted_summary,
            }
        )
        now = self._now()
        row = OpportunityProjectionDB(
            id=f"opportunity-{uuid.uuid4()}",
            employer_name=str(command.parameters["employer"]),
            title=str(command.parameters["title"]),
            location=None,
            role_family=None,
            state="discovered",
            score=None,
            score_explanation=None,
            risk_flags=[],
            evidence_refs=[evidence_contract.to_dict()],
            source_event_id="pending",
            source_event_position="pending",
            projected_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)

        # Score at creation-time, but only if an Intent already exists to
        # score against — an unset Intent must never silently default to
        # "no preference = full match". Without an Intent the opportunity is
        # simply left unscored, same as before this wiring, to be scored
        # later via an explicit `opportunities.score` command or the next
        # `intent.set` rescore pass.
        if self._scorer is not None:
            intent_row = self._db.get(IntentProjectionDB, INTENT_SINGLETON_ID)
            if intent_row is not None:
                scored = await self._scorer.score(row.id, "default")
                if not 0 <= scored.score <= 100:
                    raise ValueError("score must be between 0 and 100")
                if len(scored.explanation) > 1000:
                    raise ValueError(
                        "score explanation exceeds contract maximum"
                    )
                row.score = scored.score
                row.score_explanation = scored.explanation
                row.risk_flags = list(scored.risk_flags)
                row.state = "qualified" if scored.score >= 80 else "watching"

        return HandlerResult(
            result={"opportunity_id": row.id, "status": row.state},
            entity_type="opportunity",
            entity_ref=row.id,
            attributes={
                "state": row.state,
                "evidence_ref": evidence_contract.evidence_id,
            },
            projections=(row,),
        )

    async def _opportunities_score(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        opportunity_id = str(command.parameters["opportunity_id"])
        row = self._locked_row(OpportunityProjectionDB, opportunity_id)
        if row is None:
            raise DomainRefusal("opportunity_not_found")
        if self._scorer is None:
            raise DomainRefusal("scorer_unbound")
        scored = await self._scorer.score(
            opportunity_id,
            str(command.parameters["lens"]),
        )
        if not 0 <= scored.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if len(scored.explanation) > 1000:
            raise ValueError("score explanation exceeds contract maximum")
        row.score = scored.score
        row.score_explanation = scored.explanation
        row.risk_flags = list(scored.risk_flags)
        row.state = "qualified" if scored.score >= 80 else "watching"
        bucket_floor = min(int(scored.score) // 20 * 20, 80)
        bucket = (
            "80-100"
            if bucket_floor == 80
            else f"{bucket_floor}-{bucket_floor + 19}"
        )
        return HandlerResult(
            result={
                "opportunity_id": row.id,
                "fit_score": scored.score,
                "status": row.state,
            },
            entity_type="opportunity",
            entity_ref=row.id,
            attributes={"state": row.state, "score_bucket": bucket},
            projections=(row,),
        )

    async def _applications_create(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        opportunity_id = str(command.parameters["opportunity_id"])
        if self._db.get(OpportunityProjectionDB, opportunity_id) is None:
            raise DomainRefusal("opportunity_not_found")
        occurred_at = str(command.parameters["occurred_at"])
        now = self._now()
        row = ApplicationProjectionDB(
            id=f"application-{uuid.uuid4()}",
            opportunity_id=opportunity_id,
            state="draft",
            stage_history=[{"status": "draft", "occurred_at": occurred_at}],
            artifact_refs=[],
            next_action=None,
            next_action_deadline=None,
            source_event_id="pending",
            source_event_position="pending",
            projected_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)
        return HandlerResult(
            result={"application_id": row.id, "status": row.state},
            entity_type="application",
            entity_ref=row.id,
            attributes={"state": row.state},
            projections=(row,),
        )

    async def _applications_transition(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        application_id = str(command.parameters["application_id"])
        row = self._locked_row(ApplicationProjectionDB, application_id)
        if row is None:
            raise DomainRefusal("application_not_found")
        target = str(command.parameters["status"])
        transitions = {
            "draft": {"applied", "withdrawn", "closed"},
            "applied": {"screening", "rejected", "withdrawn", "closed"},
            "screening": {"interviewing", "rejected", "withdrawn", "closed"},
            "interviewing": {"offer", "rejected", "withdrawn", "closed"},
            "offer": {"accepted", "rejected", "withdrawn", "closed"},
            "accepted": set(),
            "rejected": set(),
            "withdrawn": set(),
            "closed": set(),
        }
        if target not in transitions[row.state]:
            raise DomainRefusal("invalid_application_transition")
        row.state = target
        row.stage_history = [
            *list(row.stage_history or []),
            {
                "status": target,
                "occurred_at": str(command.parameters["occurred_at"]),
            },
        ]
        return HandlerResult(
            result={"application_id": row.id, "status": target},
            entity_type="application",
            entity_ref=row.id,
            attributes={"state": target, "stage": target},
            projections=(row,),
        )

    async def _relationships_sync(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        opportunity_id = str(command.parameters["opportunity_id"])
        if self._db.get(OpportunityProjectionDB, opportunity_id) is None:
            raise DomainRefusal("opportunity_not_found")
        if self._relationship_resolver is None:
            raise DomainRefusal("relationship_resolver_unbound")
        dex_ref = str(command.parameters["dex_contact_ref"])
        resolved = await self._relationship_resolver.sync(
            opportunity_id,
            dex_ref,
        )
        if (
            resolved.relevance_score is not None
            and not 0 <= resolved.relevance_score <= 100
        ):
            raise ValueError("relationship relevance must be between 0 and 100")
        row = RelationshipProjectionDB(
            id=resolved.relationship_id,
            opportunity_id=opportunity_id,
            dex_contact_ref=dex_ref,
            relevance_score=resolved.relevance_score,
            relevance_reason=resolved.relevance_summary,
            source_event_id="pending",
            source_event_position="pending",
            projected_at=self._now(),
            created_at=self._now(),
            updated_at=self._now(),
        )
        self._db.add(row)
        return HandlerResult(
            result={"relationship_id": row.id},
            entity_type="relationship",
            entity_ref=row.id,
            attributes={},
            projections=(row,),
        )

    async def _outreach_prepare(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        opportunity_id = str(command.parameters["opportunity_id"])
        if self._db.get(OpportunityProjectionDB, opportunity_id) is None:
            raise DomainRefusal("opportunity_not_found")
        relationship_id = command.parameters.get("relationship_id")
        if relationship_id is not None:
            relationship = self._db.get(
                RelationshipProjectionDB,
                relationship_id,
            )
            if (
                relationship is None
                or relationship.opportunity_id != opportunity_id
            ):
                raise DomainRefusal("relationship_not_found")
        now = self._now()
        row = OutreachProjectionDB(
            id=f"outreach-{uuid.uuid4()}",
            opportunity_id=opportunity_id,
            relationship_id=relationship_id,
            state="pending_approval",
            channel=str(command.parameters["channel"]),
            message_commitment=str(
                command.parameters["message_commitment"]
            ),
            approval_contract_ref=None,
            sent_evidence_ref=None,
            source_event_id="pending",
            source_event_position="pending",
            projected_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)
        return HandlerResult(
            result={"outreach_id": row.id, "status": row.state},
            entity_type="outreach",
            entity_ref=row.id,
            attributes={
                "state": row.state,
                "commitment": row.message_commitment,
            },
            projections=(row,),
        )

    async def _outreach_approve(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        outreach_id = str(command.parameters["outreach_id"])
        row = self._locked_row(OutreachProjectionDB, outreach_id)
        if row is None:
            raise DomainRefusal("outreach_not_found")
        if row.state != "pending_approval":
            raise DomainRefusal("outreach_not_pending_approval")
        commitment = str(command.parameters["message_commitment"])
        if row.message_commitment != commitment:
            raise DomainRefusal("message_commitment_mismatch")
        now = self._now()
        approval = JobSearchApprovalDB(
            approval_id=f"approval-{uuid.uuid4()}",
            outreach_id=row.id,
            message_commitment=commitment,
            channel=row.channel,
            approved_by=command.actor_id,
            issued_at=now,
            expires_at=now + timedelta(hours=24),
            status="approved",
        )
        self._db.add(approval)
        row.state = "approved"
        row.approval_contract_ref = approval.approval_id
        return HandlerResult(
            result={
                "outreach_id": row.id,
                "approval_contract_id": approval.approval_id,
                "status": row.state,
            },
            entity_type="outreach",
            entity_ref=row.id,
            attributes={
                "state": row.state,
                "commitment": row.message_commitment,
            },
            projections=(row,),
        )

    async def _outreach_send(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        outreach_id = str(command.parameters["outreach_id"])
        approval_id = str(command.parameters["approval_contract_id"])
        row = self._locked_row(OutreachProjectionDB, outreach_id)
        if row is None:
            raise DomainRefusal("outreach_not_found")
        approval = self._locked_row(JobSearchApprovalDB, approval_id)
        if approval is None:
            raise DomainRefusal("approval_not_found", receipt_reason="policy_denied")
        if row.approval_contract_ref != approval_id:
            raise DomainRefusal(
                "approval_contract_mismatch",
                receipt_reason="policy_denied",
            )
        if approval.status != "approved":
            raise DomainRefusal("approval_inactive", receipt_reason="policy_denied")
        if approval.outreach_id != outreach_id:
            raise DomainRefusal(
                "approval_outreach_mismatch",
                receipt_reason="policy_denied",
            )
        commitment = str(command.parameters["message_commitment"])
        if (
            approval.message_commitment != commitment
            or row.message_commitment != commitment
        ):
            raise DomainRefusal(
                "approval_commitment_mismatch",
                receipt_reason="policy_denied",
            )
        channel = str(command.parameters["channel"])
        if approval.channel != channel or row.channel != channel:
            raise DomainRefusal(
                "approval_channel_mismatch",
                receipt_reason="policy_denied",
            )
        if _aware(approval.expires_at) <= _aware(self._now()):
            raise DomainRefusal(
                "approval_expired",
                receipt_reason="authority_expired",
            )
        if row.state != "approved":
            raise DomainRefusal("outreach_not_approved", receipt_reason="policy_denied")
        if self._sender is None:
            raise DomainRefusal("delivery_transport_unbound")
        evidence_ref = await self._sender.send(
            outreach_id=row.id,
            channel=channel,
            message_commitment=commitment,
            idempotency_key=command.idempotency_key,
        )
        if not evidence_ref.startswith("evidence-"):
            raise ValueError("sender must return an opaque evidence reference")
        row.state = "sent"
        row.sent_evidence_ref = evidence_ref
        return HandlerResult(
            result={
                "outreach_id": row.id,
                "status": row.state,
                "evidence_ref": evidence_ref,
            },
            entity_type="outreach",
            entity_ref=row.id,
            attributes={
                "state": row.state,
                "commitment": row.message_commitment,
                "evidence_ref": evidence_ref,
            },
            projections=(row,),
        )

    async def _outreach_cancel(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        outreach_id = str(command.parameters["outreach_id"])
        row = self._locked_row(OutreachProjectionDB, outreach_id)
        if row is None:
            raise DomainRefusal("outreach_not_found")
        if row.state not in OUTREACH_CANCEL_ALLOWED_SOURCE_STATUSES_V1:
            raise DomainRefusal("invalid_outreach_cancel_transition")
        reason = str(command.parameters["reason"])
        row.state = OUTREACH_CANCEL_TARGET_STATUS_V1
        return HandlerResult(
            result={
                "outreach_id": row.id,
                "status": row.state,
                "reason": reason,
            },
            entity_type="outreach",
            entity_ref=row.id,
            attributes={"state": row.state},
            projections=(row,),
        )

    async def _evidence_export(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        subject_type = str(command.parameters["subject_type"])
        subject_id = str(command.parameters["subject_id"])
        models = {
            "opportunity": OpportunityProjectionDB,
            "application": ApplicationProjectionDB,
            "relationship": RelationshipProjectionDB,
            "outreach": OutreachProjectionDB,
            "evidence": JobSearchEvidenceReferenceDB,
        }
        model = models.get(subject_type)
        if model is None:
            raise DomainRefusal("unsupported_evidence_subject")
        if self._db.get(model, subject_id) is None:
            raise DomainRefusal("evidence_subject_not_found")
        evidence_ref = f"evidence-export-{uuid.uuid4()}"
        return HandlerResult(
            result={
                "evidence_ref": evidence_ref,
                "profile": "accountability.v1",
            },
            entity_type="evidence",
            entity_ref=evidence_ref,
            attributes={"evidence_ref": evidence_ref},
        )

    async def _leads_create(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        params = command.parameters
        employer = str(params.get("employer") or "").strip()
        title = str(params.get("title") or "").strip()
        if not employer or not title:
            raise DomainRefusal("invalid_lead_parameters")

        now = self._now()
        lead_id = f"lead-{uuid.uuid4()}"

        fit_score = params.get("fit_score")
        if fit_score is not None:
            try:
                fit_score = float(fit_score)
            except (TypeError, ValueError):
                raise DomainRefusal("invalid_lead_parameters")
            if not 0 <= fit_score <= 100:
                raise DomainRefusal("invalid_lead_parameters")

        row = LeadDB(
            id=lead_id,
            source_board=str(params.get("source_board", "manual")),
            external_id=params.get("external_id"),
            employer=employer,
            organization_id=params.get("organization_id"),
            title=title,
            location=params.get("location"),
            remote_type=str(params.get("remote_type", "unknown")),
            salary_min=params.get("salary_min"),
            salary_max=params.get("salary_max"),
            salary_currency=str(params.get("salary_currency", "USD")),
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

        fit_score_val = (
            int(round(row.fit_score))
            if row.fit_score is not None
            else None
        )
        return HandlerResult(
            result={
                "lead_id": row.id,
                "employer": row.employer,
                "title": row.title,
                "status": row.state,
                "fit_score": fit_score_val,
            },
            entity_type="lead",
            entity_ref=row.id,
            attributes={
                "state": row.state,
            },
            projections=(row,),
        )

    async def _leads_convert(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        params = command.parameters
        lead_id = str(params.get("lead_id") or "").strip()
        if not lead_id:
            raise DomainRefusal("lead_not_found")
        lead = self._locked_row(LeadDB, lead_id)
        if lead is None:
            raise DomainRefusal("lead_not_found")

        # Fail-closed refusal if already converted or dismissed
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
        score_val = lead.fit_score
        score_explanation = (
            json.dumps(lead.match_breakdown)
            if isinstance(lead.match_breakdown, dict) and lead.match_breakdown
            else f"Converted from Lead {lead.id}"
        )
        if len(score_explanation) > 1000:
            score_explanation = score_explanation[:997] + "..."

        source_kind = (
            lead.source_board
            if lead.source_board in SOURCE_KINDS_V1
            else "manual"
        )
        evidence_dict = {
            "evidence_id": f"evidence-lead-{lead.id}",
            "source_kind": source_kind,
            "source_ref": lead.url or f"lead:{lead.id}",
            "classification": "private",
            "observed_at": _timestamp(lead.created_at),
            "commitment": f"sha256:{hashlib.sha256(lead.id.encode()).hexdigest()}",
            "redacted_summary": f"Lead converted: {lead.title} at {lead.employer}"[:240],
        }

        opp_row = OpportunityProjectionDB(
            id=opp_id,
            employer_name=lead.employer,
            title=str(params.get("custom_title") or lead.title),
            location=lead.location,
            role_family=str(params.get("target_role_family") or "engineering_leadership"),
            state="qualified" if (score_val is not None and score_val >= 80) else "watching",
            score=score_val,
            score_explanation=score_explanation,
            risk_flags=list(lead.risk_flags or []),
            evidence_refs=[evidence_dict],
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
            },
            projections=projections,
        )

    async def _organizations_create(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        params = command.parameters
        name = str(params.get("name") or "").strip()
        if not name:
            raise DomainRefusal("invalid_organization_name")

        now = self._now()
        org_id = f"organization-{uuid.uuid4()}"

        advocacy = params.get("advocacy_rating")
        if advocacy is not None:
            try:
                advocacy = float(advocacy)
            except (TypeError, ValueError):
                raise DomainRefusal("invalid_organization_parameters")
            if not 0.0 <= advocacy <= 100.0:
                raise DomainRefusal("invalid_organization_parameters")

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

    async def _organizations_update(
        self,
        command: JobSearchCommandV1,
    ) -> HandlerResult:
        params = command.parameters
        org_id = str(params.get("organization_id") or "").strip()
        if not org_id:
            raise DomainRefusal("organization_not_found")
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
                try:
                    advocacy = float(advocacy)
                except (TypeError, ValueError):
                    raise DomainRefusal("invalid_organization_parameters")
                if not 0.0 <= advocacy <= 100.0:
                    raise DomainRefusal("invalid_organization_parameters")
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
