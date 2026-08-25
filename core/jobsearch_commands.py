"""Canonical Gateway for governed job-search commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import uuid

from ravenhelm_contracts import (
    ContractHandleV1,
    CorrelationContextV1,
    JobSearchCommandV1,
    JobSearchEventV1,
)
from ravenhelm_contracts.accountability_v1 import hash_execution_receipt_v1
from ravenhelm_contracts.jobsearch_v1 import COMMAND_NAMES_V1
from sqlalchemy.orm import Session

COMMAND_NAMES_CRM: frozenset[str] = COMMAND_NAMES_V1 | frozenset(
    {
        "leads.create",
        "leads.convert",
        "organizations.create",
        "organizations.update",
    }
)

from .delegation_service import DelegationService
from .event_producer import EventProducer
from .idempotency_service import IdempotencyService
from .jobsearch_models import (
    INTENT_SINGLETON_ID,
    WORKSPACE_SINGLETON_ID,
    JobSearchCommandDB,
    JobSearchExecutionReceiptDB,
    JobSearchLifecycleEventDB,
)
from .jobsearch_nats import JobSearchTaskPublisher
from .jobsearch_receipts import ReceiptIssuer
from .models import EventType, OperationResponse
from .operation_service import OperationService
from .gateway import IdempotencyConflictError


@dataclass(frozen=True)
class JobSearchCommandRequest:
    command: str
    parameters: dict[str, object]
    actor_id: str
    idempotency_key: str
    delegation_id: str | None = None
    correlation_id: str | None = None

    def idempotency_fingerprint(self) -> str:
        envelope = {
            "tenant_id": "private",
            "actor_id": self.actor_id,
            "delegation_id": self.delegation_id,
            "command": self.command,
            "parameters": self.parameters,
        }
        return hashlib.sha256(
            json.dumps(
                envelope,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()


class JobSearchDispatchError(RuntimeError):
    """Raised when accepted intent cannot be published to JetStream."""

    def __init__(self, operation: OperationResponse):
        super().__init__("Job-search command dispatch failed")
        self.operation = operation


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.astimezone()
    return value.astimezone(timezone.utc).isoformat()


def _operation_response(db: Session, operation_id: str) -> OperationResponse:
    operation = OperationService.get_operation(db, operation_id)
    if operation is None:  # pragma: no cover - created in the same transaction
        raise RuntimeError("Persisted operation disappeared")
    return operation


def _handle(
    operation,
    status: str,
    *,
    refusal_code: str | None = None,
    refusal_reason: str | None = None,
) -> ContractHandleV1:
    payload: dict[str, object] = {
        "contract_id": operation.id,
        "operation_id": operation.id,
        "status": status,
        "submitted_at": _timestamp(operation.created_at),
        "correlation_id": operation.correlation_id,
        "status_url": f"/api/v2/operations/{operation.id}",
        "events_url": f"/api/v1/operations/{operation.id}/events",
    }
    if status == "refused":
        payload["refusal_code"] = refusal_code or "policy_denied"
        payload["refusal_reason"] = refusal_reason or "Command refused"
    return ContractHandleV1.from_dict(payload)


def _entity_for(command: JobSearchCommandV1) -> tuple[str, str]:
    bindings = {
        "workspace.initialize": ("workspace", WORKSPACE_SINGLETON_ID),
        "intent.set": ("intent", INTENT_SINGLETON_ID),
        "sources.ingest": ("evidence", None),
        "opportunities.create": ("opportunity", None),
        "opportunities.score": (
            "opportunity",
            command.parameters.get("opportunity_id"),
        ),
        "applications.create": ("application", None),
        "applications.transition": (
            "application",
            command.parameters.get("application_id"),
        ),
        "relationships.sync": ("relationship", None),
        "outreach.prepare": ("outreach", None),
        "outreach.approve": (
            "outreach",
            command.parameters.get("outreach_id"),
        ),
        "outreach.send": (
            "outreach",
            command.parameters.get("outreach_id"),
        ),
        "outreach.cancel": (
            "outreach",
            command.parameters.get("outreach_id"),
        ),
        "evidence.export": ("evidence", None),
        "leads.create": ("lead", None),
        "leads.convert": ("lead", command.parameters.get("lead_id")),
        "organizations.create": ("organization", None),
        "organizations.update": (
            "organization",
            command.parameters.get("organization_id"),
        ),
    }
    entity_type, supplied = bindings[command.command]
    if isinstance(supplied, str) and supplied.startswith(f"{entity_type}-"):
        return entity_type, supplied
    return entity_type, f"{entity_type}-{uuid.uuid4()}"


def build_jobsearch_event(
    *,
    command: JobSearchCommandV1,
    operation,
    event_id: str,
    domain_event_type: str,
    lifecycle_state: str,
    result: str,
    occurred_at: datetime,
    entity_type: str | None = None,
    entity_ref: str | None = None,
    receipt_id: str | None = None,
    attributes: dict[str, object] | None = None,
    refusal_code: str | None = None,
    refusal_reason: str | None = None,
) -> JobSearchEventV1:
    inferred_type, inferred_ref = _entity_for(command)
    context_payload = command.context.to_dict()
    context_payload["event_id"] = event_id
    if receipt_id is not None:
        context_payload["audit_ref"] = f"receipt:{receipt_id}"
    context = CorrelationContextV1.from_dict(context_payload)
    handle = _handle(
        operation,
        lifecycle_state,
        refusal_code=refusal_code,
        refusal_reason=refusal_reason,
    )
    event_payload: dict[str, object] = {
        "control_surface_event": {
            "specversion": "1.0",
            "id": event_id,
            "source": "/ravenhelm/ultradex/jobsearch",
            "type": domain_event_type,
            "subject": entity_ref or inferred_ref,
            "time": _timestamp(occurred_at),
            "schema_version": "jobsearch.v1",
            "classification": "private",
            "lifecycle_state": lifecycle_state,
            "context": context.to_dict(),
            "contract_handle": handle.to_dict(),
            "metric_labels": {
                "service": "ultradex",
                "environment": command.context.environment,
                "operation_type": command.command,
                "task_type": command.command,
                "state": lifecycle_state,
                "result": result,
                "schema_version": "jobsearch.v1",
            },
        },
        "domain_event_type": domain_event_type,
        "entity_type": entity_type or inferred_type,
        "entity_ref": entity_ref or inferred_ref,
        "attributes": {"result": result, **(attributes or {})},
    }
    if receipt_id is not None:
        event_payload["control_surface_event"]["audit_ref"] = (  # type: ignore[index]
            f"receipt:{receipt_id}"
        )
    return JobSearchEventV1.from_dict(event_payload)


class JobSearchGatewayService:
    def __init__(
        self,
        publisher: JobSearchTaskPublisher,
        receipt_issuer: ReceiptIssuer,
    ) -> None:
        self._publisher = publisher
        self._receipt_issuer = receipt_issuer

    def _command(
        self,
        request: JobSearchCommandRequest,
        operation_id: str,
    ) -> JobSearchCommandV1:
        if request.command not in COMMAND_NAMES_CRM:
            raise ValueError("command is not a canonical job-search command")
        request_id = f"request-{uuid.uuid4()}"
        context = CorrelationContextV1.from_dict(
            {
                "tenant_id": "private",
                "operation_id": operation_id,
                "contract_id": operation_id,
                "correlation_id": (
                    request.correlation_id or f"correlation-{uuid.uuid4()}"
                ),
                "causation_id": request_id,
                "execution_id": f"execution-{uuid.uuid4()}",
                "actor_id": request.actor_id,
                "request_id": request_id,
                "trace_id": f"trace-{uuid.uuid4().hex}",
                "service_name": "ultradex-api",
                "service_version": os.getenv(
                    "ULTRADEX_SERVICE_VERSION",
                    "2.0.0",
                ),
                "deployment_sha": os.getenv(
                    "ULTRADEX_DEPLOYMENT_SHA",
                    "unverified-local",
                ),
                "environment": os.getenv("ULTRADEX_ENVIRONMENT", "local"),
                "contract_version": "jobsearch.v1",
                "schema_version": "control-surface.v1",
                "action_id": f"action-{uuid.uuid4()}",
                "task_id": f"task-{uuid.uuid4()}",
                **(
                    {"delegation_id": request.delegation_id}
                    if request.delegation_id is not None
                    else {}
                ),
            }
        )
        return JobSearchCommandV1.from_dict(
            {
                "command_id": f"command-{uuid.uuid4()}",
                "command": request.command,
                "actor_id": request.actor_id,
                "idempotency_key": request.idempotency_key,
                "context": context.to_dict(),
                "parameters": request.parameters,
            }
        )

    async def submit_command(
        self,
        db: Session,
        request: JobSearchCommandRequest,
    ) -> OperationResponse:
        operation_id = str(uuid.uuid4())
        command = self._command(request, operation_id)
        if request.delegation_id:
            if not DelegationService.validate_delegation(
                db,
                request.actor_id,
                request.command,
                request.delegation_id,
            ):
                raise PermissionError("Command authority refused")

        fingerprint = request.idempotency_fingerprint()
        try:
            operation = OperationService.create_operation(
                db,
                command=request.command,
                correlation_id=command.context.correlation_id,
                operation_id=operation_id,
                commit=False,
            )
            db.flush()
            claimed = IdempotencyService.claim_key(
                db,
                request.idempotency_key,
                operation_id,
            )
            if not claimed:
                cached = IdempotencyService.get_cached_binding(
                    db,
                    request.idempotency_key,
                )
                cached_operation = (
                    None
                    if cached is None
                    else OperationService.get_operation(db, cached[0])
                )
                db.rollback()
                if (
                    cached is None
                    or cached[1] != fingerprint
                    or cached_operation is None
                ):
                    raise IdempotencyConflictError(
                        "Idempotency key is bound to another command envelope"
                    )
                return cached_operation

            db.add(
                JobSearchCommandDB(
                    operation_id=operation_id,
                    command_id=command.command_id,
                    command_name=command.command,
                    actor_id=command.actor_id,
                    delegation_id=request.delegation_id,
                    idempotency_key=command.idempotency_key,
                    context=command.context.to_dict(),
                    parameters=dict(command.parameters),
                    created_at=_utcnow(),
                    dispatched_at=None,
                )
            )
            EventProducer.emit(
                db,
                EventType.OPERATION_ACCEPTED,
                operation_id,
                {
                    "command": command.command,
                    "actor_id": command.actor_id,
                    "delegation_id": request.delegation_id,
                    "idempotency_fingerprint": fingerprint,
                },
                commit=False,
            )
            accepted = build_jobsearch_event(
                command=command,
                operation=operation,
                event_id=f"event-{uuid.uuid4()}",
                domain_event_type=f"jobsearch.{command.command}.accepted.v1",
                lifecycle_state="accepted",
                result="unknown",
                occurred_at=_utcnow(),
            )
            db.add(
                JobSearchLifecycleEventDB(
                    event_id=accepted.control_surface_event.id,
                    operation_id=operation_id,
                    event_type=accepted.domain_event_type,
                    payload=accepted.to_dict(),
                    occurred_at=_utcnow(),
                    published_at=None,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        try:
            await self._publisher.publish_lifecycle(accepted)
            self._best_effort_mark_event_published(
                db,
                accepted.control_surface_event.id,
            )
            await self._publisher.publish_command(command)
            self._best_effort_mark_command_dispatched(
                db,
                operation_id,
            )
        except Exception as error:
            terminal = self._record_dispatch_failure(db, command)
            try:
                await self._publisher.publish_lifecycle(terminal)
                self._mark_event_published(
                    db,
                    terminal.control_surface_event.id,
                )
            except Exception:
                # The durable unpublished row is the retry/outbox boundary.
                db.rollback()
            raise JobSearchDispatchError(
                _operation_response(db, operation_id)
            ) from error
        return _operation_response(db, operation_id)

    @staticmethod
    def _mark_event_published(db: Session, event_id: str) -> None:
        row = db.get(JobSearchLifecycleEventDB, event_id)
        if row is None:  # pragma: no cover - persisted immediately before publish
            raise RuntimeError("Published lifecycle event disappeared")
        row.published_at = _utcnow()
        db.commit()

    @classmethod
    def _best_effort_mark_event_published(
        cls,
        db: Session,
        event_id: str,
    ) -> None:
        try:
            cls._mark_event_published(db, event_id)
        except Exception:
            # JetStream already acknowledged the event. Leaving the outbox row
            # unpublished makes recovery replay it with the same Nats-Msg-Id.
            db.rollback()

    @staticmethod
    def _best_effort_mark_command_dispatched(
        db: Session,
        operation_id: str,
    ) -> None:
        try:
            row = db.get(JobSearchCommandDB, operation_id)
            if row is None:
                raise RuntimeError("Dispatched command disappeared")
            row.dispatched_at = _utcnow()
            db.commit()
        except Exception:
            # A publish ACK is authoritative. The durable outbox may replay this
            # command, and JetStream/executor idempotency makes that safe.
            db.rollback()

    def _record_dispatch_failure(
        self,
        db: Session,
        command: JobSearchCommandV1,
    ) -> JobSearchEventV1:
        now = _utcnow()
        operation = OperationService.fail_operation(
            db,
            command.context.operation_id,
            "JetStream command dispatch failed",
            commit=False,
        )
        event_id = self._receipt_issuer.new_opaque_id()
        receipt = self._receipt_issuer.issue(
            command=command,
            event_id=event_id,
            sequence=1,
            status="failed",
            started_at=operation.created_at,
            completed_at=now,
            result=None,
            reason_code="executor_failure",
        )
        terminal = build_jobsearch_event(
            command=command,
            operation=operation,
            event_id=event_id,
            domain_event_type="jobsearch.command.dispatch_failed.v1",
            lifecycle_state="failed",
            result="failure",
            occurred_at=now,
            receipt_id=receipt.receipt_id,
        )
        EventProducer.emit(
            db,
            EventType.TASK_FAILED,
            operation.id,
            {"reason_code": "queue_dispatch_failed"},
            commit=False,
        )
        db.add_all(
            [
                JobSearchLifecycleEventDB(
                    event_id=event_id,
                    operation_id=operation.id,
                    event_type=terminal.domain_event_type,
                    payload=terminal.to_dict(),
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
        db.commit()
        return terminal
