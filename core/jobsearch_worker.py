"""Message-level worker behavior for governed job-search JetStream tasks."""

from __future__ import annotations

import json

from ravenhelm_contracts import JobSearchCommandV1

from .jobsearch_executors import JobSearchExecutor, RetryableCommandError
from .jobsearch_nats import JobSearchTaskPublisher


class JobSearchWorker:
    """Validate one NATS message and ACK only after terminal publication."""

    def __init__(
        self,
        executor: JobSearchExecutor,
        publisher: JobSearchTaskPublisher,
        *,
        retry_delay_seconds: int = 30,
    ) -> None:
        self._executor = executor
        self._publisher = publisher
        self._retry_delay_seconds = retry_delay_seconds

    async def handle_message(self, message) -> None:
        try:
            payload = json.loads(message.data)
            if not isinstance(payload, dict):
                raise ValueError("task payload must be an object")
            command = JobSearchCommandV1.from_dict(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
            await message.term()
            return

        attempt = int(getattr(message.metadata, "num_delivered", 1))
        try:
            outcome = await self._executor.execute(
                command,
                attempt=attempt,
            )
        except RetryableCommandError:
            await message.nak(delay=self._retry_delay_seconds)
            return

        await self._publisher.publish_lifecycle(outcome.event)
        self._executor.mark_event_published(
            outcome.event.control_surface_event.id
        )
        await message.ack()
