"""Message-level worker behavior for governed job-search JetStream tasks."""

from __future__ import annotations

import asyncio
import json
import os

import nats
from nats.errors import TimeoutError as NATSTimeoutError

from ravenhelm_contracts import JobSearchCommandV1

from .database import Database
from .jobsearch_executors import JobSearchExecutor, RetryableCommandError
from .jobsearch_nats import (
    COMMAND_SUBJECT_PREFIX,
    STREAM_NAME,
    JobSearchNATSPublisher,
    JobSearchTaskPublisher,
)
from .jobsearch_receipts import ReceiptIssuer


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


class JobSearchPullConsumer:
    """Durable pull consumer for the bounded job-search command subjects."""

    def __init__(
        self,
        *,
        url: str,
        worker: JobSearchWorker,
        durable: str = "ultradex-jobsearch-v1",
        batch_size: int = 10,
        fetch_timeout_seconds: float = 1.0,
    ) -> None:
        self._url = url
        self._worker = worker
        self._durable = durable
        self._batch_size = batch_size
        self._fetch_timeout_seconds = fetch_timeout_seconds
        self._nc = None
        self._subscription = None

    async def connect(self) -> None:
        self._nc = await nats.connect(
            servers=[self._url],
            name="ultradex-jobsearch-worker",
            max_reconnect_attempts=-1,
        )
        jetstream = self._nc.jetstream()
        self._subscription = await jetstream.pull_subscribe(
            f"{COMMAND_SUBJECT_PREFIX}.*",
            durable=self._durable,
            stream=STREAM_NAME,
        )

    async def run_once(self) -> int:
        if self._subscription is None:
            raise RuntimeError("job-search pull consumer is not connected")
        try:
            messages = await self._subscription.fetch(
                batch=self._batch_size,
                timeout=self._fetch_timeout_seconds,
            )
        except NATSTimeoutError:
            return 0
        for message in messages:
            await self._worker.handle_message(message)
        return len(messages)

    async def run_forever(self) -> None:
        while True:
            await self.run_once()

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
            self._nc = None
            self._subscription = None


async def run_jobsearch_worker() -> None:
    """Run the safe worker; external adapter ports remain unbound."""
    nats_url = os.getenv("NATS_URL")
    if not nats_url:
        raise ValueError("NATS_URL is required for the job-search worker")
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://ultradex:ultradex_dev_password@localhost:5432/ultradex",
    )
    database = Database(database_url)
    database.init()
    session = database.get_session()
    publisher = JobSearchNATSPublisher(url=nats_url)
    consumer = None
    try:
        await publisher.connect()
        executor = JobSearchExecutor(session, ReceiptIssuer.from_env())
        worker = JobSearchWorker(executor, publisher)
        consumer = JobSearchPullConsumer(url=nats_url, worker=worker)
        await consumer.connect()
        await consumer.run_forever()
    finally:
        if consumer is not None:
            await consumer.close()
        await publisher.close()
        session.close()
        database.close()


if __name__ == "__main__":
    asyncio.run(run_jobsearch_worker())
