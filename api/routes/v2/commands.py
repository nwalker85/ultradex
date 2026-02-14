"""v2 command endpoints (async, 202 Accepted)"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from arq.connections import ArqRedis

from core import (
    get_db,
    OperationResponse,
    GatewayService,
    CommandRequest,
)
from ...dependencies import get_redis

router = APIRouter()


@router.post("/contacts/commands/analyze", status_code=202)
async def analyze_v2(
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis)
) -> OperationResponse:
    """
    Submit analyze command for async execution.

    Returns 202 Accepted immediately with operation_id for polling.
    """
    try:
        gateway = GatewayService(redis)

        command = CommandRequest(
            command="analyze",
            parameters={"limit": limit} if limit else {},
        )

        operation = await gateway.submit_command(db, command)
        return operation

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting analyze command: {str(e)}"
        )


@router.post("/contacts/commands/sync", status_code=202)
async def sync_v2(
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis)
) -> OperationResponse:
    """
    Submit sync command for async execution.

    Returns 202 Accepted immediately with operation_id for polling.
    """
    try:
        gateway = GatewayService(redis)

        command = CommandRequest(
            command="sync",
            parameters={},
        )

        operation = await gateway.submit_command(db, command)
        return operation

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting sync command: {str(e)}"
        )
