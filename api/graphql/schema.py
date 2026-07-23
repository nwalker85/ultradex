"""GraphQL schema for Ultradex"""

from datetime import datetime
from typing import Optional, List
import strawberry
from fastapi import Depends
from strawberry.scalars import JSON
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core import (
    JobSearchProjectionRepository,
    OperationDB,
    OperationEventDB,
    get_db,
)
from api.auth import AuthenticatedPrincipal, require_read_principal
from .jobsearch_types import (
    Application,
    ApplicationPage,
    Opportunity,
    OpportunityPage,
    Outreach,
    OutreachPage,
    Relationship,
    RelationshipPage,
)


async def get_graphql_context(
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
) -> dict[str, object]:
    """Provide the read-only GraphQL projection session."""
    return {"db": db, "principal": principal}


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
    freshness: Optional[ProjectionFreshnessGQL]

    @classmethod
    def from_db(cls, op: OperationDB) -> "OperationGQL":
        """Convert OperationDB to GraphQL type"""
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
            # U01 has no durable projector checkpoint. Null is more truthful
            # than manufacturing a zero-lag/fresh projection at request time.
            freshness=None,
        )


@strawberry.type
class Query:
    """GraphQL query root"""

    @strawberry.field
    def opportunity(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Opportunity | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_opportunity(id)
        return (
            None
            if projection is None
            else Opportunity.from_contract(projection)
        )

    @strawberry.field
    def opportunities(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
    ) -> OpportunityPage:
        page = JobSearchProjectionRepository(
            info.context["db"]
        ).list_opportunities(
            first=first,
            after=after,
            status=status,
        )
        return OpportunityPage.from_page(page)

    @strawberry.field
    def application(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Application | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_application(id)
        return (
            None
            if projection is None
            else Application.from_contract(projection)
        )

    @strawberry.field
    def applications(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
        opportunity_id: str | None = None,
    ) -> ApplicationPage:
        page = JobSearchProjectionRepository(
            info.context["db"]
        ).list_applications(
            first=first,
            after=after,
            status=status,
            opportunity_id=opportunity_id,
        )
        return ApplicationPage.from_page(page)

    @strawberry.field
    def relationship(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Relationship | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_relationship(id)
        return (
            None
            if projection is None
            else Relationship.from_contract(projection)
        )

    @strawberry.field
    def relationships(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        opportunity_id: str | None = None,
    ) -> RelationshipPage:
        page = JobSearchProjectionRepository(
            info.context["db"]
        ).list_relationships(
            first=first,
            after=after,
            opportunity_id=opportunity_id,
        )
        return RelationshipPage.from_page(page)

    @strawberry.field
    def outreach_item(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Outreach | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_outreach(id)
        return (
            None
            if projection is None
            else Outreach.from_contract(projection)
        )

    @strawberry.field
    def outreach(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
        opportunity_id: str | None = None,
    ) -> OutreachPage:
        page = JobSearchProjectionRepository(info.context["db"]).list_outreach(
            first=first,
            after=after,
            status=status,
            opportunity_id=opportunity_id,
        )
        return OutreachPage.from_page(page)

    @strawberry.field
    def operation(self, info: strawberry.Info, id: str) -> Optional[OperationGQL]:
        """Get a single operation by ID"""
        db: Session = info.context["db"]
        op = db.query(OperationDB).filter(OperationDB.id == id).first()
        if not op:
            return None
        return OperationGQL.from_db(op)

    @strawberry.field
    def operations(
        self,
        info: strawberry.Info,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> List[OperationGQL]:
        """List operations with optional filtering"""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        db: Session = info.context["db"]
        query = db.query(OperationDB).order_by(OperationDB.created_at.desc())
        if status:
            query = query.filter(OperationDB.status == status)
        ops = query.limit(limit).all()
        return [OperationGQL.from_db(op) for op in ops]

    @strawberry.field
    def events(
        self,
        info: strawberry.Info,
        operation_id: str,
        first: int = 50,
        after: Optional[int] = None,
    ) -> List[OperationEventGQL]:
        """Get one stable, bounded page of lifecycle events."""
        if not 1 <= first <= 100:
            raise ValueError("first must be between 1 and 100")
        db: Session = info.context["db"]
        query = db.query(OperationEventDB).filter(
            OperationEventDB.operation_id == operation_id
        )
        if after is not None:
            cursor = db.query(OperationEventDB).filter(
                OperationEventDB.id == after,
                OperationEventDB.operation_id == operation_id,
            ).first()
            if cursor is None:
                raise ValueError("after cursor does not exist for operation")
            query = query.filter(
                or_(
                    OperationEventDB.timestamp > cursor.timestamp,
                    and_(
                        OperationEventDB.timestamp == cursor.timestamp,
                        OperationEventDB.id > cursor.id,
                    ),
                )
            )
        events = query.order_by(
            OperationEventDB.timestamp.asc(),
            OperationEventDB.id.asc(),
        ).limit(first).all()
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
