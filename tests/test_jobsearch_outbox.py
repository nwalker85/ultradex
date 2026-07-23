from __future__ import annotations

import pytest

from core.jobsearch_commands import (
    JobSearchCommandRequest,
    JobSearchDispatchError,
    JobSearchGatewayService,
)
from core.jobsearch_models import (
    JobSearchCommandDB,
    JobSearchLifecycleEventDB,
)
from core.jobsearch_outbox import JobSearchOutboxDispatcher
from tests.conftest import FakeJobSearchPublisher


PARAMETERS = {
    "employer": "Example",
    "title": "Platform Engineer",
    "source_evidence_id": "evidence-01",
}


@pytest.mark.asyncio
async def test_outbox_recovers_accepted_event_and_command_after_crash_gap(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    operation = await JobSearchGatewayService(
        fake_jobsearch_publisher,
        receipt_issuer,
    ).submit_command(
        db_session,
        JobSearchCommandRequest(
            command="opportunities.create",
            parameters=PARAMETERS,
            actor_id="operator:test",
            idempotency_key="outbox-recovery",
        ),
    )
    command_row = db_session.get(JobSearchCommandDB, operation.id)
    event_row = (
        db_session.query(JobSearchLifecycleEventDB)
        .filter_by(operation_id=operation.id)
        .one()
    )
    command_row.dispatched_at = None
    event_row.published_at = None
    db_session.commit()
    fake_jobsearch_publisher.commands.clear()
    fake_jobsearch_publisher.events.clear()

    dispatched = await JobSearchOutboxDispatcher(
        db_session,
        fake_jobsearch_publisher,
    ).dispatch_pending()

    assert dispatched == 2
    assert [event.domain_event_type for event in fake_jobsearch_publisher.events] == [
        "jobsearch.opportunities.create.accepted.v1"
    ]
    assert [command.command for command in fake_jobsearch_publisher.commands] == [
        "opportunities.create"
    ]
    db_session.refresh(command_row)
    db_session.refresh(event_row)
    assert command_row.dispatched_at is not None
    assert event_row.published_at is not None


@pytest.mark.asyncio
async def test_outbox_never_dispatches_a_terminally_failed_command(
    db_session,
    receipt_issuer,
):
    failing = FakeJobSearchPublisher(fail_commands=True)
    with pytest.raises(JobSearchDispatchError):
        await JobSearchGatewayService(failing, receipt_issuer).submit_command(
            db_session,
            JobSearchCommandRequest(
                command="opportunities.create",
                parameters=PARAMETERS,
                actor_id="operator:test",
                idempotency_key="outbox-failed",
            ),
        )
    command_row = db_session.query(JobSearchCommandDB).one()
    assert command_row.dispatched_at is None
    publisher = FakeJobSearchPublisher()

    dispatched = await JobSearchOutboxDispatcher(
        db_session,
        publisher,
    ).dispatch_pending()

    assert dispatched == 0
    assert publisher.commands == []
