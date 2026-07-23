"""Operation tracking endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from core import (
    get_db,
    OperationService,
    OperationResponse,
    OperationEvent,
    EventProducer,
)

router = APIRouter()


@router.get("/operations/{operation_id}", response_model=OperationResponse)
async def get_operation(
    operation_id: str,
    db: Session = Depends(get_db)
):
    """Get operation status by ID"""
    try:
        operation = OperationService.get_operation(db, operation_id)
        if not operation:
            raise HTTPException(status_code=404, detail="Operation not found")
        return operation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching operation: {str(e)}")


@router.get("/operations", response_model=List[OperationResponse])
async def list_operations(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List recent operations"""
    try:
        from core import OperationDB
        operations = db.query(OperationDB).order_by(
            OperationDB.created_at.desc()
        ).limit(limit).all()

        return [
            OperationResponse(
                id=op.id,
                correlation_id=op.correlation_id,
                command=op.command,
                status=op.status,
                created_at=op.created_at,
                started_at=op.started_at,
                completed_at=op.completed_at,
                result=op.result,
                error=op.error
            )
            for op in operations
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching operations: {str(e)}")


@router.get("/operations/{operation_id}/events", response_model=List[OperationEvent])
async def get_operation_events(
    operation_id: str,
    first: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get audit trail of events for an operation"""
    try:
        events = EventProducer.get_events(db, operation_id, limit=first)
        return [
            OperationEvent(
                id=event.id,
                operation_id=event.operation_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                payload=event.payload or {}
            )
            for event in events
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching events: {str(e)}")
