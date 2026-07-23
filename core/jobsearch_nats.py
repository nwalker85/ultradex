"""NATS JetStream task and lifecycle publisher for the job-search domain."""

from __future__ import annotations

import json
import re
from typing import Protocol

import nats
from nats.js.errors import APIError, NotFoundError
from ravenhelm_contracts import JobSearchCommandV1, JobSearchEventV1
from ravenhelm_contracts.jobsearch_v1 import COMMAND_NAMES_V1


STREAM_NAME = "ULTRADEX_JOBSEARCH_V1"
COMMAND_SUBJECT_PREFIX = "ultradex.jobsearch.commands.v1"
EVENT_SUBJECT_PREFIX = "ultradex.jobsearch.events.v1"
REQUIRED_STREAM_SUBJECTS = (
    f"{COMMAND_SUBJECT_PREFIX}.*",
    f"{EVENT_SUBJECT_PREFIX}.*",
)
COMMAND_SUBJECTS: dict[str, str] = {
    command: f"{COMMAND_SUBJECT_PREFIX}.{command.replace('.', '-')}"
    for command in sorted(COMMAND_NAMES_V1)
}
EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")


def lifecycle_subject(event_type: str) -> str:
    if not EVENT_TYPE_PATTERN.fullmatch(event_type):
        raise ValueError("event type must be a bounded catalog value")
    return f"{EVENT_SUBJECT_PREFIX}.{event_type.replace('.', '-')}"


class JobSearchTaskPublisher(Protocol):
    async def publish_command(self, command: JobSearchCommandV1) -> None: ...

    async def publish_lifecycle(self, event: JobSearchEventV1) -> None: ...


class UnavailableJobSearchPublisher:
    """Fail-closed port used when JetStream has no live binding."""

    def __init__(self, reason: str = "NATS is not configured") -> None:
        self._reason = reason

    async def publish_command(self, command: JobSearchCommandV1) -> None:
        raise ConnectionError(self._reason)

    async def publish_lifecycle(self, event: JobSearchEventV1) -> None:
        raise ConnectionError(self._reason)

    async def close(self) -> None:
        return None


async def ensure_jobsearch_stream(jetstream) -> None:
    """Create or reconcile the shared stream under concurrent service startup."""

    try:
        info = await jetstream.stream_info(STREAM_NAME)
    except NotFoundError:
        try:
            await jetstream.add_stream(
                name=STREAM_NAME,
                subjects=list(REQUIRED_STREAM_SUBJECTS),
                storage="file",
            )
            return
        except APIError as create_error:
            # The API and worker can discover a missing stream simultaneously.
            # Re-read after a losing create race; preserve the create error when
            # no competing service actually established the stream.
            try:
                info = await jetstream.stream_info(STREAM_NAME)
            except NotFoundError:
                raise create_error

    configured = set(info.config.subjects or ())
    required = set(REQUIRED_STREAM_SUBJECTS)
    if not required.issubset(configured):
        await jetstream.update_stream(
            config=info.config.evolve(
                subjects=sorted(configured | required),
            )
        )


class JobSearchNATSPublisher:
    """Publish validated contracts to a bounded JetStream subject catalog."""

    def __init__(self, *, url: str, jetstream=None) -> None:
        self._url = url
        self._nc = None
        self._js = jetstream

    async def connect(self) -> None:
        if self._js is not None:
            return
        self._nc = await nats.connect(
            servers=[self._url],
            name="ultradex-jobsearch-api",
            max_reconnect_attempts=-1,
        )
        self._js = self._nc.jetstream()
        await ensure_jobsearch_stream(self._js)

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
            self._nc = None
            self._js = None

    def _connected_jetstream(self):
        if self._js is None:
            raise ConnectionError("NATS JetStream publisher is not connected")
        return self._js

    async def publish_command(self, command: JobSearchCommandV1) -> None:
        subject = COMMAND_SUBJECTS.get(command.command)
        if subject is None:  # pragma: no cover - shared contract already rejects it
            raise ValueError("command is not registered")
        payload = json.dumps(
            command.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        await self._connected_jetstream().publish(
            subject,
            payload,
            headers={"Nats-Msg-Id": command.idempotency_key},
        )

    async def publish_lifecycle(self, event: JobSearchEventV1) -> None:
        payload = json.dumps(
            event.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        await self._connected_jetstream().publish(
            lifecycle_subject(event.domain_event_type),
            payload,
            headers={
                "Nats-Msg-Id": event.control_surface_event.id,
            },
        )
