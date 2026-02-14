"""GraphQL schema for Ultradex"""

from datetime import datetime
from typing import Optional, List
import strawberry
from sqlalchemy.orm import Session

from core import (
    OperationDB,
    OperationEventDB,
    EventProducer,
)


@strawberry.type
class OperationEventGQL:
    """GraphQL type for OperationEvent"""
    id: int
    operation_id: str
    event_type: str
    timestamp: datetime
    payload: Optional[strawberry.JSON] = None


@strawberry.type
class OperationGQL:
    """GraphQL type for Operation"""
    id: str
    correlation_id: Optional[str]
    command: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[strawberry.JSON]
    error: Optional[str]
    events: Optional[List[OperationEventGQL]] = None

    @classmethod
    def from_db(cls, db: Session, op: OperationDB) -> "OperationGQL":
        """Convert OperationDB to GraphQL type"""
        events = EventProducer.get_events(db, op.id)
        events_gql = [
            OperationEventGQL(
                id=e.id,
                operation_id=e.operation_id,
                event_type=e.event_type,
                timestamp=e.timestamp,
                payload=e.payload
            )
            for e in events
        ]
        return cls(
            id=op.id,
            correlation_id=op.correlation_id,
            command=op.command,
            status=op.status,
            created_at=op.created_at,
            started_at=op.started_at,
            completed_at=op.completed_at,
            result=op.result,
            error=op.error,
            events=events_gql
        )


@strawberry.type
class Query:
    """GraphQL query root"""

    @strawberry.field
    def operation(self, id: str, db: Session) -> Optional[OperationGQL]:
        """Get a single operation by ID"""
        op = db.query(OperationDB).filter(OperationDB.id == id).first()
        if not op:
            return None
        return OperationGQL.from_db(db, op)

    @strawberry.field
    def operations(
        self,
        limit: int = 10,
        status: Optional[str] = None,
        db: Session = None
    ) -> List[OperationGQL]:
        """List operations with optional filtering"""
        query = db.query(OperationDB).order_by(OperationDB.created_at.desc())
        if status:
            query = query.filter(OperationDB.status == status)
        ops = query.limit(limit).all()
        return [OperationGQL.from_db(db, op) for op in ops]

    @strawberry.field
    def events(self, operation_id: str, db: Session) -> List[OperationEventGQL]:
        """Get events for an operation"""
        events = EventProducer.get_events(db, operation_id)
        return [
            OperationEventGQL(
                id=e.id,
                operation_id=e.operation_id,
                event_type=e.event_type,
                timestamp=e.timestamp,
                payload=e.payload
            )
            for e in events
        ]


schema = strawberry.Schema(query=Query)
