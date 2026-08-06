from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

import httpx
import pytest
from ravenhelm_contracts import ContractHandleV1
from ravenhelm_contracts.accountability_v1 import ExecutionReceiptV1

from api.dependencies import get_jobsearch_publisher, get_receipt_issuer
from api.main import app
from core import (
    Database,
    JobSearchCommandDB,
    JobSearchEvidenceReferenceDB,
    JobSearchExecutionReceiptDB,
    JobSearchExecutor,
    JobSearchLifecycleEventDB,
    JobSearchNATSPublisher,
    JobSearchPullConsumer,
    JobSearchWorker,
    OpportunityProjectionDB,
    OperationDB,
    ProjectionCheckpointDB,
    ReceiptIssuer,
    get_db,
    verify_receipt_signature,
)


def _resolve_nats_server() -> Path | None:
    found = shutil.which("nats-server")
    if found:
        return Path(found)
    for candidate in (
        Path("/opt/homebrew/bin/nats-server"),
        Path("/usr/local/bin/nats-server"),
        Path("/usr/bin/nats-server"),
    ):
        if candidate.is_file():
            return candidate
    return None


NATS_SERVER = _resolve_nats_server()
COMMITMENT = f"sha256:{'4' * 64}"


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture
def isolated_nats(tmp_path: Path) -> str:
    """Start a private port-0 JetStream and always reap its subprocess."""

    if NATS_SERVER is None or not NATS_SERVER.is_file():
        pytest.skip("nats-server binary not available in this environment")
    store_dir = tmp_path / "nats-store"
    ports_dir = tmp_path / "nats-ports"
    config_path = tmp_path / "nats.conf"
    store_dir.mkdir()
    ports_dir.mkdir()
    config_path.write_text("host: 127.0.0.1\nport: 0\n")
    process = subprocess.Popen(
        [
            str(NATS_SERVER),
            "--config",
            str(config_path),
            "--jetstream",
            "--store_dir",
            str(store_dir),
            "--ports_file_dir",
            str(ports_dir),
            "--server_name",
            f"ultradex-test-{uuid.uuid4().hex}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(
                    f"isolated NATS exited before readiness: {process.returncode}"
                )
            ports_files = list(ports_dir.glob("*.ports"))
            if ports_files:
                ports = json.loads(ports_files[0].read_text())
                urls = ports.get("nats")
                if isinstance(urls, list) and len(urls) == 1:
                    yield str(urls[0])
                    return
            time.sleep(0.05)
        pytest.fail("isolated NATS did not publish its dynamic client port")
    finally:
        _stop_process(process)


def _seed_harness_state(database: Database) -> tuple[str, str]:
    """Seed only synthetic evidence and empty-projection freshness markers."""

    now = datetime.now(timezone.utc)
    evidence_id = f"evidence-synthetic-{uuid.uuid4().hex}"
    source_ref = f"web-synthetic-{uuid.uuid4().hex}"
    with database.get_session() as session:
        session.add(
            JobSearchEvidenceReferenceDB(
                evidence_id=evidence_id,
                source_kind="web",
                source_ref=source_ref,
                classification="private",
                observed_at=now,
                commitment=COMMITMENT,
                redacted_summary="Synthetic public role metadata.",
                created_at=now,
            )
        )
        # These harness-only checkpoints represent explicit, empty, freshly
        # verified projections. opportunities.create stamps its own checkpoint.
        for projection_type in ("applications", "relationships", "outreach"):
            source_event_id = (
                f"event-harness-empty-{projection_type}-{uuid.uuid4().hex}"
            )
            session.add(
                ProjectionCheckpointDB(
                    projection_type=projection_type,
                    source_event_id=source_event_id,
                    source_event_position=f"HARNESS:{source_event_id}",
                    projected_at=now,
                    lag_ms=0,
                    status="fresh",
                )
            )
        session.commit()
    return evidence_id, source_ref


@pytest.mark.asyncio
async def test_scoped_operator_command_completes_isolated_signed_runtime_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_nats: str,
) -> None:
    database = Database(f"sqlite:///{tmp_path / 'runtime.db'}")
    database.init()
    evidence_id, evidence_source_ref = _seed_harness_state(database)
    issuer = ReceiptIssuer(
        hmac_key=b"h" * 32,
        signing_private_key=bytes(range(32)),
        key_id=f"pairwise:v1:{'C' * 22}",
        executor_pairwise_id=f"pairwise:v1:{'D' * 22}",
    )
    command_token = f"synthetic-command-token-{uuid.uuid4().hex}"
    command_subject = f"career-operator:synthetic:{uuid.uuid4().hex}"
    monkeypatch.setenv("ULTRADEX_COMMAND_TOKEN", command_token)
    monkeypatch.setenv("ULTRADEX_COMMAND_ID", command_subject)

    publisher = JobSearchNATSPublisher(url=isolated_nats)
    worker_session = database.get_session()
    consumer: JobSearchPullConsumer | None = None

    def override_db():
        session = database.get_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_jobsearch_publisher] = lambda: publisher
    app.dependency_overrides[get_receipt_issuer] = lambda: issuer
    try:
        await publisher.connect()
        consumer = JobSearchPullConsumer(
            url=isolated_nats,
            worker=JobSearchWorker(
                JobSearchExecutor(worker_session, issuer),
                publisher,
            ),
            durable=f"ultradex-test-{uuid.uuid4().hex}",
            batch_size=10,
            fetch_timeout_seconds=0.25,
        )
        await consumer.connect()

        idempotency_key = f"synthetic-idempotency-{uuid.uuid4().hex}"
        correlation_id = f"synthetic-correlation-{uuid.uuid4().hex}"
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://ultradex.synthetic.invalid",
            headers={"Authorization": f"Bearer {command_token}"},
        ) as client:
            response = await client.post(
                "/api/v2/job-search/commands/opportunities.create",
                headers={
                    "Idempotency-Key": idempotency_key,
                    "X-Correlation-Id": correlation_id,
                },
                json={
                    "employer": "Synthetic Systems",
                    "title": "Synthetic Platform Operator",
                    "source_evidence_id": evidence_id,
                },
            )
            assert response.status_code == 202
            handle = ContractHandleV1.from_dict(response.json())

            delivered = await consumer.run_once()

            graphql = await client.post(
                "/api/graphql",
                json={
                    "query": """
                        query RuntimeProof($operationId: String!) {
                          opportunities(first: 25) {
                            items {
                              opportunityId
                              employer
                              title
                              status
                              evidenceRefs { evidenceId commitment }
                              freshness {
                                sourceEventId
                                sourceEventPosition
                                lagMs
                                status
                              }
                            }
                          }
                          executionReceipt(operationId: $operationId) {
                            receiptId
                            operationId
                            eventId
                            status
                            receiptHash
                            proofStatus
                            payload
                          }
                        }
                    """,
                    "variables": {
                        "operationId": handle.operation_id,
                    },
                },
            )
            delegation_admin = await client.get("/api/v2/delegations")

        assert delivered == 1

        with database.get_session() as session:
            commands = session.query(JobSearchCommandDB).all()
            assert len(commands) == 1
            assert commands[0].operation_id == handle.operation_id
            assert commands[0].idempotency_key == idempotency_key
            assert commands[0].actor_id == command_subject

        with database.get_session() as session:
            operation = session.get(OperationDB, handle.operation_id)
            assert operation is not None
            assert operation.status == "completed"
            assert operation.correlation_id == correlation_id
            opportunity_id = str(operation.result["opportunity_id"])

        with database.get_session() as session:
            opportunity = session.get(OpportunityProjectionDB, opportunity_id)
            assert opportunity is not None
            assert len(opportunity.evidence_refs) == 1
            assert opportunity.evidence_refs[0]["evidence_id"] == evidence_id
            assert opportunity.evidence_refs[0]["source_kind"] == "web"
            assert (
                opportunity.evidence_refs[0]["source_ref"]
                == evidence_source_ref
            )
            assert opportunity.evidence_refs[0]["commitment"] == COMMITMENT
            checkpoint = session.get(ProjectionCheckpointDB, "opportunities")
            assert checkpoint is not None
            assert checkpoint.status == "fresh"
            assert checkpoint.source_event_id == opportunity.source_event_id
            assert checkpoint.source_event_position == (
                f"JOBSEARCH:{opportunity.source_event_id}"
            )
            assert checkpoint.lag_ms == 0

        with database.get_session() as session:
            events = (
                session.query(JobSearchLifecycleEventDB)
                .filter_by(operation_id=handle.operation_id)
                .order_by(JobSearchLifecycleEventDB.occurred_at)
                .all()
            )
            assert [event.event_type for event in events] == [
                "jobsearch.opportunities.create.accepted.v1",
                "jobsearch.opportunities.create.succeeded.v1",
            ]
            assert all(event.published_at is not None for event in events)
            terminal_event_id = events[-1].event_id

        with database.get_session() as session:
            receipts = (
                session.query(JobSearchExecutionReceiptDB)
                .filter_by(operation_id=handle.operation_id)
                .all()
            )
            assert len(receipts) == 1
            receipt_row = receipts[0]
            assert receipt_row.status == "succeeded"
            assert receipt_row.event_id == terminal_event_id
            receipt = ExecutionReceiptV1.from_dict(receipt_row.payload)
            receipt_id = receipt_row.receipt_id
            receipt_hash = receipt_row.receipt_hash
            assert receipt.event_id == terminal_event_id
            verify_receipt_signature(receipt, issuer.public_key_bytes)

        assert graphql.status_code == 200
        assert "errors" not in graphql.json()
        data = graphql.json()["data"]
        assert data["opportunities"]["items"] == [
            {
                "opportunityId": opportunity_id,
                "employer": "Synthetic Systems",
                "title": "Synthetic Platform Operator",
                "status": "discovered",
                "evidenceRefs": [
                    {
                        "evidenceId": evidence_id,
                        "commitment": COMMITMENT,
                    }
                ],
                "freshness": {
                    "sourceEventId": terminal_event_id,
                    "sourceEventPosition": f"JOBSEARCH:{terminal_event_id}",
                    "lagMs": 0.0,
                    "status": "fresh",
                },
            }
        ]
        assert data["executionReceipt"]["operationId"] == handle.operation_id
        assert data["executionReceipt"]["receiptId"] == receipt_id
        assert data["executionReceipt"]["eventId"] == terminal_event_id
        assert data["executionReceipt"]["status"] == "succeeded"
        assert data["executionReceipt"]["receiptHash"] == receipt_hash
        assert data["executionReceipt"]["proofStatus"] == "server-recorded"
        assert data["executionReceipt"]["payload"] == receipt.to_dict()
        assert delegation_admin.status_code == 403
    finally:
        app.dependency_overrides.clear()
        if consumer is not None:
            await consumer.close()
        await publisher.close()
        worker_session.close()
        database.close()
