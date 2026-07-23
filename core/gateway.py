"""Gateway service for command dispatch."""

import hashlib
import json
from typing import Optional, Any
from arq.connections import ArqRedis
from sqlalchemy.orm import Session
from .operation_service import OperationService
from .event_producer import EventProducer
from .delegation_service import DelegationService
from .idempotency_service import IdempotencyService
from .models import OperationResponse, EventType


class CommandRequest:
    def __init__(
        self,
        command: str,
        parameters: dict,
        actor_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        self.command = command
        self.parameters = parameters
        self.actor_id = actor_id
        self.delegation_id = delegation_id
        self.idempotency_key = idempotency_key
        self.correlation_id = correlation_id

    def idempotency_fingerprint(self) -> str:
        """Bind a caller key to the complete private command envelope."""
        envelope = {
            "tenant_id": "private",
            "actor_id": self.actor_id,
            "delegation_id": self.delegation_id,
            "command": self.command,
            "parameters": self.parameters,
        }
        encoded = json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class IdempotencyConflictError(ValueError):
    """Raised when a caller reuses a key for a different command envelope."""


class QueueDispatchError(RuntimeError):
    """Raised after a command is durably recorded but cannot be dispatched."""

    def __init__(self, operation: OperationResponse):
        super().__init__("Command queue unavailable")
        self.operation = operation


class GatewayService:
    def __init__(self, redis: ArqRedis):
        self.redis = redis

    async def submit_command(
        self,
        db: Session,
        command: CommandRequest
    ) -> OperationResponse:
        """
        Submit a command to the queue.

        Returns:
            OperationResponse with operation_id for polling
        """
        # 1. Validate delegated execution before consulting an idempotency cache.
        # Actor identity is correlation context; it does not itself assert delegated
        # authority. Authentication remains an API-layer responsibility.
        if command.delegation_id:
            if not command.actor_id:
                raise PermissionError("Delegated execution requires actor_id")
            authorized = DelegationService.validate_delegation(
                db,
                command.actor_id,
                command.command,
                command.delegation_id,
            )
            if not authorized:
                raise PermissionError(
                    f"Actor {command.actor_id} not authorized for {command.command}"
                )

        # 2. A caller-supplied key is valid only for the exact command envelope.
        if command.idempotency_key:
            cached = IdempotencyService.get_cached_binding(
                db,
                command.idempotency_key,
            )
            if cached:
                cached_op_id, cached_fingerprint = cached
                if cached_fingerprint != command.idempotency_fingerprint():
                    raise IdempotencyConflictError(
                        "Idempotency key is already bound to another command envelope"
                    )
                operation = OperationService.get_operation(db, cached_op_id)
                if operation:
                    return operation

        # 3. Create operation record (pending status)
        operation = OperationService.create_operation(
            db,
            command=command.command,
            correlation_id=command.correlation_id
        )

        # 4. Record idempotency key
        if command.idempotency_key:
            IdempotencyService.record_key(
                db,
                command.idempotency_key,
                operation.id
            )

        # 5. Emit operation.accepted event
        EventProducer.emit(
            db,
            EventType.OPERATION_ACCEPTED,
            operation.id,
            {
                "command": command.command,
                "actor_id": command.actor_id,
                "delegation_id": command.delegation_id,
                "idempotency_fingerprint": command.idempotency_fingerprint(),
            }
        )

        # 6. Dispatch to ARQ queue
        task_name = f"{command.command}_task"

        try:
            await self.redis.enqueue_job(
                task_name,
                operation.id,
                command.parameters
            )
        except Exception as error:
            OperationService.fail_operation(
                db,
                operation.id,
                f"Queue dispatch failed: {type(error).__name__}",
            )
            EventProducer.emit(
                db,
                EventType.TASK_FAILED,
                operation.id,
                {"reason_code": "queue_dispatch_failed"},
            )
            failed = OperationService.get_operation(db, operation.id)
            if failed is None:  # pragma: no cover - operation was just persisted
                raise RuntimeError("Failed operation disappeared") from error
            raise QueueDispatchError(failed) from error

        # 7. Return operation details for polling
        return OperationResponse(
            id=operation.id,
            correlation_id=operation.correlation_id,
            command=command.command,
            status=operation.status,
            created_at=operation.created_at,
            started_at=operation.started_at,
            completed_at=operation.completed_at,
            result=operation.result,
            error=operation.error
        )
