from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest
from cryptography.exceptions import InvalidSignature
from ravenhelm_contracts import CorrelationContextV1, JobSearchCommandV1
from ravenhelm_contracts.accountability_v1 import ExecutionReceiptV1

from core.jobsearch_receipts import ReceiptIssuer, verify_receipt_signature


STARTED = datetime(2026, 7, 23, 13, 5, 44, tzinfo=timezone.utc)
COMPLETED = datetime(2026, 7, 23, 13, 6, 59, tzinfo=timezone.utc)
PRIVATE_KEY = bytes(range(32))
HMAC_KEY = b"h" * 32
KEY_ID = f"pairwise:v1:{'A' * 22}"
EXECUTOR_ID = f"pairwise:v1:{'B' * 22}"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _command() -> JobSearchCommandV1:
    context = CorrelationContextV1.from_dict(
        {
            "tenant_id": "private",
            "operation_id": "operation-01",
            "contract_id": "operation-01",
            "correlation_id": "correlation-01",
            "causation_id": "causation-01",
            "execution_id": "execution-01",
            "actor_id": "operator:test",
            "request_id": "request-01",
            "trace_id": "trace-01",
            "service_name": "ultradex-api",
            "service_version": "2.0.0",
            "deployment_sha": "a" * 40,
            "environment": "test",
            "contract_version": "jobsearch.v1",
            "schema_version": "control-surface.v1",
        }
    )
    return JobSearchCommandV1.from_dict(
        {
            "command_id": "command-01",
            "command": "opportunities.create",
            "actor_id": "operator:test",
            "idempotency_key": "create-opportunity-01",
            "context": context.to_dict(),
            "parameters": {
                "employer": "Example",
                "title": "Platform Engineer",
                "source_evidence_id": "evidence-01",
            },
        }
    )


@pytest.fixture
def issuer() -> ReceiptIssuer:
    return ReceiptIssuer(
        hmac_key=HMAC_KEY,
        signing_private_key=PRIVATE_KEY,
        key_id=KEY_ID,
        executor_pairwise_id=EXECUTOR_ID,
    )


def test_success_receipt_is_signed_structurally_valid_and_private(issuer):
    receipt = issuer.issue(
        command=_command(),
        event_id=issuer.new_opaque_id(),
        sequence=0,
        status="succeeded",
        started_at=STARTED,
        completed_at=COMPLETED,
        result={"opportunity_id": "opportunity-01"},
        reason_code=None,
    )

    validated = ExecutionReceiptV1.from_dict(receipt.to_dict())
    verify_receipt_signature(validated, issuer.public_key_bytes)

    assert validated.status == "succeeded"
    assert validated.result_commitment is not None
    assert validated.reason_code is None
    assert validated.started_at == "2026-07-23T13:05:00.000Z"
    assert validated.completed_at == "2026-07-23T13:06:00.000Z"
    wire = str(validated.to_dict())
    assert "operator:test" not in wire
    assert "create-opportunity-01" not in wire
    assert "Example" not in wire
    assert validated.tenant_scope.scheme == "hmac_sha256_v1"
    assert validated.action_commitment.scheme == "hmac_sha256_v1"


@pytest.mark.parametrize(
    ("status", "reason_code"),
    [
        ("failed", "executor_failure"),
        ("refused", "safety_refusal"),
        ("refused", "policy_denied"),
    ],
)
def test_terminal_non_success_receipts_use_v1_reason_catalog(
    issuer,
    status,
    reason_code,
):
    receipt = issuer.issue(
        command=_command(),
        event_id=issuer.new_opaque_id(),
        sequence=0,
        status=status,
        started_at=STARTED,
        completed_at=COMPLETED,
        result=None,
        reason_code=reason_code,
    )

    validated = ExecutionReceiptV1.from_dict(receipt.to_dict())
    assert validated.status == status
    assert validated.reason_code == reason_code
    assert validated.result_commitment is None
    verify_receipt_signature(validated, issuer.public_key_bytes)


def test_receipt_signature_rejects_structurally_valid_tampering(issuer):
    receipt = issuer.issue(
        command=_command(),
        event_id=issuer.new_opaque_id(),
        sequence=0,
        status="succeeded",
        started_at=STARTED,
        completed_at=COMPLETED,
        result={"opportunity_id": "opportunity-01"},
        reason_code=None,
    )
    tampered = receipt.to_dict()
    tampered["executor_pairwise_id"] = f"pairwise:v1:{'C' * 22}"
    validated = ExecutionReceiptV1.from_dict(tampered)

    with pytest.raises(InvalidSignature):
        verify_receipt_signature(validated, issuer.public_key_bytes)


def test_receipt_issuer_loads_secrets_from_environment(monkeypatch):
    monkeypatch.setenv("ULTRADEX_ACCOUNTABILITY_HMAC_KEY", _b64url(HMAC_KEY))
    monkeypatch.setenv(
        "ULTRADEX_RECEIPT_ED25519_PRIVATE_KEY",
        _b64url(PRIVATE_KEY),
    )
    monkeypatch.setenv("ULTRADEX_RECEIPT_KEY_ID", KEY_ID)
    monkeypatch.setenv("ULTRADEX_EXECUTOR_PAIRWISE_ID", EXECUTOR_ID)

    issuer = ReceiptIssuer.from_env()

    assert issuer.public_key_bytes


def test_receipt_issuer_refuses_missing_or_short_secrets(monkeypatch):
    for name in (
        "ULTRADEX_ACCOUNTABILITY_HMAC_KEY",
        "ULTRADEX_RECEIPT_ED25519_PRIVATE_KEY",
        "ULTRADEX_RECEIPT_KEY_ID",
        "ULTRADEX_EXECUTOR_PAIRWISE_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="accountability"):
        ReceiptIssuer.from_env()

    monkeypatch.setenv("ULTRADEX_ACCOUNTABILITY_HMAC_KEY", _b64url(b"short"))
    monkeypatch.setenv(
        "ULTRADEX_RECEIPT_ED25519_PRIVATE_KEY",
        _b64url(PRIVATE_KEY),
    )
    monkeypatch.setenv("ULTRADEX_RECEIPT_KEY_ID", KEY_ID)
    monkeypatch.setenv("ULTRADEX_EXECUTOR_PAIRWISE_ID", EXECUTOR_ID)
    with pytest.raises(ValueError, match="at least 32"):
        ReceiptIssuer.from_env()
