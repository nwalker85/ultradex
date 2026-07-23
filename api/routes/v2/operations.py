"""v2 operation endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from core import (
    get_db,
    OperationService,
    OperationResponse,
)

router = APIRouter()


@router.get("/operations/{operation_id}", response_model=OperationResponse)
async def get_operation_v2(
    operation_id: str,
    db: Session = Depends(get_db)
):
    """Get operation status by ID (v2)"""
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
async def list_operations_v2(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List recent operations (v2)"""
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
