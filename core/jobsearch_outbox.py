"""Recovery dispatcher for accepted commands and unpublished lifecycle facts."""

from __future__ import annotations

from datetime import datetime, timezone

from ravenhelm_contracts import JobSearchCommandV1, JobSearchEventV1
from sqlalchemy.orm import Session

from .jobsearch_models import (
    JobSearchCommandDB,
    JobSearchLifecycleEventDB,
)
from .jobsearch_nats import JobSearchTaskPublisher
from .models import OperationDB, OperationStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobSearchOutboxDispatcher:
    """Project durable database intent into JetStream after crash gaps."""

    def __init__(
        self,
        db: Session,
        publisher: JobSearchTaskPublisher,
    ) -> None:
        self._db = db
        self._publisher = publisher

    async def dispatch_pending(self, *, limit: int = 100) -> int:
        if limit < 1:
            raise ValueError("outbox dispatch limit must be positive")
        dispatched = 0
        events = (
            self._db.query(JobSearchLifecycleEventDB)
            .filter(JobSearchLifecycleEventDB.published_at.is_(None))
            .order_by(
                JobSearchLifecycleEventDB.occurred_at.asc(),
                JobSearchLifecycleEventDB.event_id.asc(),
            )
            .limit(limit)
            .all()
        )
        for row in events:
            await self._publisher.publish_lifecycle(
                JobSearchEventV1.from_dict(row.payload)
            )
            row.published_at = _utcnow()
            self._db.commit()
            dispatched += 1

        remaining = max(limit - dispatched, 0)
        if remaining == 0:
            return dispatched
        commands = (
            self._db.query(JobSearchCommandDB)
            .join(
                OperationDB,
                OperationDB.id == JobSearchCommandDB.operation_id,
            )
            .filter(
                JobSearchCommandDB.dispatched_at.is_(None),
                OperationDB.status.in_(
                    [
                        OperationStatus.PENDING,
                        OperationStatus.RUNNING,
                    ]
                ),
            )
            .order_by(JobSearchCommandDB.created_at.asc())
            .limit(remaining)
            .all()
        )
        for row in commands:
            command = JobSearchCommandV1.from_dict(
                {
                    "command_id": row.command_id,
                    "command": row.command_name,
                    "actor_id": row.actor_id,
                    "idempotency_key": row.idempotency_key,
                    "context": row.context,
                    "parameters": row.parameters,
                }
            )
            await self._publisher.publish_command(command)
            row.dispatched_at = _utcnow()
            self._db.commit()
            dispatched += 1
        return dispatched
