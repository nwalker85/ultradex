"""Closed executor registry for governed job-search commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from ravenhelm_contracts.jobsearch_v1 import COMMAND_NAMES_V1
from sqlalchemy.orm import Session

from .event_producer import EventProducer
from .jobsearch_commands import build_jobsearch_event
from .jobsearch_models import (
    ApplicationProjectionDB,
    JobSearchApprovalDB,
    JobSearchCommandDB,
    JobSearchEvidenceReferenceDB,
    JobSearchExecutionReceiptDB,
    JobSearchLifecycleEventDB,
    OpportunityProjectionDB,
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
            "sources.ingest": self._sources_ingest,
            "opportunities.create": self._opportunities_create,
            "opportunities.score": self._opportunities_score,
            "applications.transition": self._applications_transition,
            "relationships.sync": self._relationships_sync,
            "outreach.prepare": self._outreach_prepare,
            "outreach.approve": self._outreach_approve,
            "outreach.send": self._outreach_send,
            "evidence.export": self._evidence_export,
        }
        if frozenset(self._handlers) != COMMAND_NAMES_V1:
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
