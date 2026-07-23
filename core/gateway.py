"""Gateway service for command dispatch"""

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
        # 1. Check idempotency key
        if command.idempotency_key:
            cached_op_id = IdempotencyService.get_cached_operation(
                db,
                command.idempotency_key
            )
            if cached_op_id:
                # Return cached operation
                operation = OperationService.get_operation(db, cached_op_id)
                if operation:
                    return operation

        # 2. Validate delegated execution when an explicit delegation is provided.
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
        except Exception as e:
            # If queue fails, mark operation as failed
            OperationService.fail_operation(db, operation.id, f"Queue dispatch failed: {str(e)}")
            raise

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
