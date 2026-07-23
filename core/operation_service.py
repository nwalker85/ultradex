"""Operation tracking service"""

import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from .models import OperationDB, OperationStatus, OperationResponse


class OperationService:
    @staticmethod
    def create_operation(
        db: Session,
        command: str,
        correlation_id: str = None,
        *,
        commit: bool = True,
    ) -> OperationDB:
        """Create a new operation record"""
        operation = OperationDB(
            id=str(uuid.uuid4()),
            correlation_id=correlation_id or str(uuid.uuid4()),
            command=command,
            status=OperationStatus.PENDING
        )
        db.add(operation)
        if commit:
            db.commit()
            db.refresh(operation)
        return operation

    @staticmethod
    def start_operation(db: Session, operation_id: str) -> OperationDB:
        """Mark operation as running"""
        operation = db.query(OperationDB).filter(
            OperationDB.id == operation_id
        ).first()
        if operation:
            operation.status = OperationStatus.RUNNING
            operation.started_at = datetime.now()
            db.commit()
            db.refresh(operation)
        return operation

    @staticmethod
    def complete_operation(
        db: Session,
        operation_id: str,
        result: dict
    ) -> OperationDB:
        """Mark operation as completed with result"""
        operation = db.query(OperationDB).filter(
            OperationDB.id == operation_id
        ).first()
        if operation:
            operation.status = OperationStatus.COMPLETED
            operation.completed_at = datetime.now()
            operation.result = result
            db.commit()
            db.refresh(operation)
        return operation

    @staticmethod
    def fail_operation(
        db: Session,
        operation_id: str,
        error: str
    ) -> OperationDB:
        """Mark operation as failed with error"""
        operation = db.query(OperationDB).filter(
            OperationDB.id == operation_id
        ).first()
        if operation:
            operation.status = OperationStatus.FAILED
            operation.completed_at = datetime.now()
            operation.error = error
            db.commit()
            db.refresh(operation)
        return operation

    @staticmethod
    def get_operation(db: Session, operation_id: str) -> OperationResponse:
        """Get operation by ID"""
        operation = db.query(OperationDB).filter(
            OperationDB.id == operation_id
        ).first()
        if operation:
            return OperationResponse(
                id=operation.id,
                correlation_id=operation.correlation_id,
                command=operation.command,
                status=operation.status,
                created_at=operation.created_at,
                started_at=operation.started_at,
                completed_at=operation.completed_at,
                result=operation.result,
                error=operation.error
            )
        return None
