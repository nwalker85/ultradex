"""v2 command endpoints (async, 202 Accepted)."""

from datetime import timezone
import json
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from ravenhelm_contracts import CONTROL_SURFACE_V1_SCHEMA_PATHS, ContractHandleV1
from sqlalchemy.orm import Session
from arq.connections import ArqRedis

from core import (
    get_db,
    GatewayService,
    CommandRequest,
)
from ...dependencies import get_redis

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


def _accepted_handle(operation) -> dict[str, object]:
    submitted_at = operation.created_at
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=timezone.utc)
    return ContractHandleV1(
        contract_id=operation.id,
        operation_id=operation.id,
        status="accepted",
        submitted_at=submitted_at.isoformat(),
        correlation_id=operation.correlation_id or operation.id,
        status_url=f"/api/v2/operations/{operation.id}",
        events_url=f"/api/v1/operations/{operation.id}/events",
    ).to_dict()


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
    correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis)
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
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        operation = await gateway.submit_command(db, command)
        return _accepted_handle(operation)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting analyze command: {str(e)}"
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
    correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-Id"),
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis)
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
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        operation = await gateway.submit_command(db, command)
        return _accepted_handle(operation)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting sync command: {str(e)}"
        )
