from __future__ import annotations

import pytest

from core import CommandRequest, DelegationService, GatewayService


@pytest.mark.asyncio
async def test_gateway_binds_delegated_execution_to_the_exact_delegation(
    db_session,
    fake_redis,
):
    DelegationService.create_delegation(
        db_session,
        delegator="operator:nate",
        delegatee="agent:researcher",
        allowed_actions=["analyze"],
    )
    command = CommandRequest(
        command="analyze",
        parameters={},
        actor_id="agent:researcher",
        delegation_id="delegation:not-the-real-one",
    )

    with pytest.raises(PermissionError):
        await GatewayService(fake_redis).submit_command(db_session, command)

    assert fake_redis.enqueued == []
