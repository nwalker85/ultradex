"""GraphQL schema for Ultradex"""

from datetime import datetime, timezone
from typing import Optional, List
import strawberry
from fastapi import Depends
from strawberry.scalars import JSON
from sqlalchemy.orm import Session

from core import (
    OperationDB,
    OperationEventDB,
    EventProducer,
    get_db,
)


async def get_graphql_context(db: Session = Depends(get_db)) -> dict[str, Session]:
    """Provide the read-only GraphQL projection session."""
    return {"db": db}


@strawberry.type
class OperationEventGQL:
    """GraphQL type for OperationEvent"""
    id: int
    operation_id: str
    event_type: str
    timestamp: datetime
    payload: Optional[JSON] = None


@strawberry.type
class ProjectionFreshnessGQL:
    """Freshness metadata for a read projection."""

    source_event_id: str
    source_event_position: str
    projected_at: datetime
    lag_ms: float
    status: str


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
    result: Optional[JSON]
    error: Optional[str]
    freshness: ProjectionFreshnessGQL
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
        if events:
            source_event_id = str(events[-1].id)
            source_event_position = str(events[-1].id)
        else:
            source_event_id = f"operation:{op.id}"
            source_event_position = "legacy:operation"
        freshness = ProjectionFreshnessGQL(
            source_event_id=source_event_id,
            source_event_position=source_event_position,
            projected_at=datetime.now(timezone.utc),
            lag_ms=0.0,
            status="fresh",
        )
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
            freshness=freshness,
            events=events_gql
        )


@strawberry.type
class Query:
    """GraphQL query root"""

    @strawberry.field
    def operation(self, info: strawberry.Info, id: str) -> Optional[OperationGQL]:
        """Get a single operation by ID"""
        db: Session = info.context["db"]
        op = db.query(OperationDB).filter(OperationDB.id == id).first()
        if not op:
            return None
        return OperationGQL.from_db(db, op)

    @strawberry.field
    def operations(
        self,
        info: strawberry.Info,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> List[OperationGQL]:
        """List operations with optional filtering"""
        db: Session = info.context["db"]
        query = db.query(OperationDB).order_by(OperationDB.created_at.desc())
        if status:
            query = query.filter(OperationDB.status == status)
        ops = query.limit(limit).all()
        return [OperationGQL.from_db(db, op) for op in ops]

    @strawberry.field
    def events(
        self,
        info: strawberry.Info,
        operation_id: str,
    ) -> List[OperationEventGQL]:
        """Get events for an operation"""
        db: Session = info.context["db"]
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
