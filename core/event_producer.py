"""Event producer for operation audit trail"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from .models import OperationEventDB, EventType


class EventProducer:
    @staticmethod
    def emit(
        db: Session,
        event_type: EventType,
        operation_id: str,
        payload: Optional[dict] = None
    ) -> OperationEventDB:
        """
        Emit an event to the audit trail.

        Args:
            db: Database session
            event_type: Type of event (operation.accepted, task.started, etc.)
            operation_id: Operation ID this event is for
            payload: Optional event data
        """
        event = OperationEventDB(
            operation_id=operation_id,
            event_type=event_type,
            timestamp=datetime.now(),
            payload=payload or {}
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_events(
        db: Session,
        operation_id: str,
        limit: Optional[int] = None,
    ) -> list[OperationEventDB]:
        """
        Get all events for an operation in chronological order.
        """
        query = db.query(OperationEventDB).filter(
            OperationEventDB.operation_id == operation_id
        ).order_by(OperationEventDB.timestamp.asc(), OperationEventDB.id.asc())
        if limit is not None:
            query = query.limit(limit)
        return query.all()
