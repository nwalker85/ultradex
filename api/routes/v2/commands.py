"""v2 command endpoints (async, 202 Accepted)."""

from datetime import timezone
import json
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from ravenhelm_contracts import CONTROL_SURFACE_V1_SCHEMA_PATHS, ContractHandleV1
from sqlalchemy.orm import Session
from arq.connections import ArqRedis

from core import (
    get_db,
    GatewayService,
    IdempotencyConflictError,
    QueueDispatchError,
    CommandRequest,
)
from ...dependencies import get_redis
from ...auth import AuthenticatedPrincipal, require_command_principal

router = APIRouter()
CONTRACT_HANDLE_RESPONSE = {
    202: {
        "description": "Command accepted and bound to a governed contract handle.",
        "content": {
            "application/json": {
                "schema": json.loads(
                    CONTROL_SURFACE_V1_SCHEMA_PATHS["contract_handle"].read_text()
                )
            }
        },
    }
}


class AnalyzeCommandBody(BaseModel):
    limit: Optional[int] = Field(default=None, ge=1)


def _contract_handle(operation) -> dict[str, object]:
    submitted_at = operation.created_at
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.astimezone()
    submitted_at = submitted_at.astimezone(timezone.utc)
    status = {
        "pending": "accepted",
        "completed": "succeeded",
    }.get(str(operation.status), str(operation.status))
    payload = {
        "contract_id": operation.id,
        "operation_id": operation.id,
        "status": status,
        "submitted_at": submitted_at.isoformat(),
        "correlation_id": operation.correlation_id or operation.id,
        "status_url": f"/api/v2/operations/{operation.id}",
        "events_url": f"/api/v1/operations/{operation.id}/events",
    }
    return ContractHandleV1.from_dict(payload).to_dict()


_accepted_handle = _contract_handle


def _submission_response(operation):
    payload = _contract_handle(operation)
    if payload["status"] == "failed":
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.post(
    "/contacts/commands/analyze",
    status_code=202,
    response_model=None,
    responses=CONTRACT_HANDLE_RESPONSE,
)
async def analyze_v2(
    body: Optional[AnalyzeCommandBody] = Body(default=None),
    limit: Optional[int] = Query(default=None, ge=1),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    actor_id: Optional[str] = Header(default=None, alias="X-Actor-Id"),
    delegation_id: Optional[str] = Header(default=None, alias="X-Delegation-Id"),
    correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-Id"),
    principal: AuthenticatedPrincipal = Depends(require_command_principal),
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis),
) -> dict[str, object]:
    """
    Submit analyze command for async execution.

    Returns 202 Accepted immediately with operation_id for polling.
    """
    try:
        gateway = GatewayService(redis)

        requested_limit = body.limit if body and body.limit is not None else limit
        command = CommandRequest(
            command="analyze",
            parameters={"limit": requested_limit} if requested_limit is not None else {},
            idempotency_key=idempotency_key,
            actor_id=principal.subject,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

        operation = await gateway.submit_command(db, command)
        return _submission_response(operation)

    except IdempotencyConflictError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": "Idempotency key is bound to another command envelope",
            },
        )
    except QueueDispatchError as error:
        return JSONResponse(status_code=503, content=_contract_handle(error.operation))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Command authority refused")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error submitting analyze command",
        )


@router.post(
    "/contacts/commands/sync",
    status_code=202,
    response_model=None,
    responses=CONTRACT_HANDLE_RESPONSE,
)
async def sync_v2(
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    actor_id: Optional[str] = Header(default=None, alias="X-Actor-Id"),
    delegation_id: Optional[str] = Header(default=None, alias="X-Delegation-Id"),
    correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-Id"),
    principal: AuthenticatedPrincipal = Depends(require_command_principal),
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis),
) -> dict[str, object]:
    """
    Submit sync command for async execution.

    Returns 202 Accepted immediately with operation_id for polling.
    """
    try:
        gateway = GatewayService(redis)

        command = CommandRequest(
            command="sync",
            parameters={},
            idempotency_key=idempotency_key,
            actor_id=principal.subject,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

        operation = await gateway.submit_command(db, command)
        return _submission_response(operation)

    except IdempotencyConflictError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": "Idempotency key is bound to another command envelope",
            },
        )
    except QueueDispatchError as error:
        return JSONResponse(status_code=503, content=_contract_handle(error.operation))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Command authority refused")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error submitting sync command",
        )
