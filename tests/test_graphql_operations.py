from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest
from ravenhelm_contracts import ProjectionFreshnessV1

from api.main import app
from api.graphql.schema import schema
from core import EventProducer, EventType, OperationDB, get_db


@pytest.mark.asyncio
async def test_graphql_reads_operation_and_chronological_events(db_session):
    operation = OperationDB(
        id="op-graphql",
        correlation_id="corr-graphql",
        command="analyze",
        status="pending",
        created_at=datetime(2026, 7, 22, 12, 0, 0),
    )
    db_session.add(operation)
    db_session.commit()
    second = EventProducer.emit(
        db_session,
        EventType.TASK_STARTED,
        operation.id,
        {"order": 2},
    )
    first = EventProducer.emit(
        db_session,
        EventType.OPERATION_ACCEPTED,
        operation.id,
        {"order": 1},
    )
    first.timestamp = second.timestamp - timedelta(seconds=1)
    db_session.commit()

    result = await schema.execute(
        """
        query Operation($id: String!) {
          operation(id: $id) {
            id
            status
            freshness {
              sourceEventId
              sourceEventPosition
              projectedAt
              lagMs
              status
            }
            events { eventType payload }
          }
        }
        """,
        variable_values={"id": operation.id},
        context_value={"db": db_session},
    )

    assert result.errors is None
    freshness = ProjectionFreshnessV1.from_dict(
        {
            "source_event_id": result.data["operation"]["freshness"]["sourceEventId"],
            "source_event_position": result.data["operation"]["freshness"]["sourceEventPosition"],
            "projected_at": result.data["operation"]["freshness"]["projectedAt"],
            "lag_ms": result.data["operation"]["freshness"]["lagMs"],
            "status": result.data["operation"]["freshness"]["status"],
        }
    )
    assert freshness.status == "fresh"
    assert result.data["operation"]["events"] == [
        {"eventType": "operation.accepted", "payload": {"order": 1}},
        {"eventType": "task.started", "payload": {"order": 2}},
    ]
    assert {
        "id": result.data["operation"]["id"],
        "status": result.data["operation"]["status"],
    } == {
        "id": "op-graphql",
        "status": "pending",
    }


@pytest.mark.asyncio
async def test_graphql_filters_operation_projection_without_mutations(db_session):
    for index, status in enumerate(("pending", "completed", "pending")):
        db_session.add(
            OperationDB(
                id=f"op-{index}",
                correlation_id=f"corr-{index}",
                command="sync",
                status=status,
                created_at=datetime(2026, 7, 22, 12, index, 0),
            )
        )
    db_session.commit()

    result = await schema.execute(
        """
        query { operations(status: "pending", limit: 1) { id status } }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    assert result.data == {"operations": [{"id": "op-2", "status": "pending"}]}
    assert schema._schema.mutation_type is None


@pytest.mark.asyncio
async def test_mounted_graphql_route_uses_the_database_dependency(db_session):
    db_session.add(
        OperationDB(
            id="op-http",
            correlation_id="corr-http",
            command="sync",
            status="pending",
            created_at=datetime(2026, 7, 22, 13, 0, 0),
        )
    )
    db_session.commit()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/graphql",
                json={
                    "query": "query($id: String!) { operation(id: $id) { id status } }",
                    "variables": {"id": "op-http"},
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "data": {"operation": {"id": "op-http", "status": "pending"}}
    }
