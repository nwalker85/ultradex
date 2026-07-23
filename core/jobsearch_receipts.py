"""Privacy-preserving signed execution receipts for job-search commands."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import os
import re
import secrets
from typing import Literal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from ravenhelm_contracts import JobSearchCommandV1
from ravenhelm_contracts.accountability_v1 import (
    ACCOUNTABILITY_CONTRACT_VERSION,
    ExecutionReceiptV1,
    canonical_accountability_bytes,
    execution_receipt_signing_bytes_v1,
)


PAIRWISE_ID_PATTERN = re.compile(r"^pairwise:v1:[A-Za-z0-9_-]{22,86}$")
PURPOSE = "jobsearch_operation"
ReceiptStatus = Literal["succeeded", "failed", "refused"]


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_b64url(value: str, label: str) -> bytes:
    if not value:
        raise ValueError(f"Missing {label} accountability configuration")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as error:
        raise ValueError(f"{label} must be canonical base64url") from error


def _whole_minute(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("receipt timestamps must be timezone-aware")
    utc = value.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:00.000Z")


class ReceiptIssuer:
    """Issue accountability.v1 receipts without exposing private identifiers."""

    def __init__(
        self,
        *,
        hmac_key: bytes,
        signing_private_key: bytes,
        key_id: str,
        executor_pairwise_id: str,
    ) -> None:
        if len(hmac_key) < 32:
            raise ValueError("accountability HMAC key must contain at least 32 bytes")
        if len(signing_private_key) != 32:
            raise ValueError("receipt Ed25519 private key must contain exactly 32 bytes")
        if not PAIRWISE_ID_PATTERN.fullmatch(key_id):
            raise ValueError("receipt key ID must be a pairwise:v1 identifier")
        if not PAIRWISE_ID_PATTERN.fullmatch(executor_pairwise_id):
            raise ValueError("executor ID must be a pairwise:v1 identifier")
        self._hmac_key = bytes(hmac_key)
        self._signing_key = Ed25519PrivateKey.from_private_bytes(
            signing_private_key
        )
        self._key_id = key_id
        self._executor_pairwise_id = executor_pairwise_id

    @classmethod
    def from_env(cls) -> "ReceiptIssuer":
        hmac_value = os.getenv("ULTRADEX_ACCOUNTABILITY_HMAC_KEY", "")
        signing_value = os.getenv("ULTRADEX_RECEIPT_ED25519_PRIVATE_KEY", "")
        key_id = os.getenv("ULTRADEX_RECEIPT_KEY_ID", "")
        executor_id = os.getenv("ULTRADEX_EXECUTOR_PAIRWISE_ID", "")
        if not all((hmac_value, signing_value, key_id, executor_id)):
            raise ValueError("Missing accountability receipt configuration")
        return cls(
            hmac_key=_decode_b64url(
                hmac_value,
                "ULTRADEX_ACCOUNTABILITY_HMAC_KEY",
            ),
            signing_private_key=_decode_b64url(
                signing_value,
                "ULTRADEX_RECEIPT_ED25519_PRIVATE_KEY",
            ),
            key_id=key_id,
            executor_pairwise_id=executor_id,
        )

    @property
    def public_key_bytes(self) -> bytes:
        return self._signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @staticmethod
    def new_opaque_id() -> str:
        return f"opaque:v1:{_b64url(secrets.token_bytes(16))}"

    def _opaque_reference(self, domain: str, value: str) -> str:
        token = hmac.digest(
            self._hmac_key,
            f"{ACCOUNTABILITY_CONTRACT_VERSION}\0{domain}\0{value}".encode(),
            "sha256",
        )
        return f"opaque:v1:{_b64url(token[:16])}"

    def _pairwise_reference(self, domain: str, value: str) -> str:
        token = hmac.digest(
            self._hmac_key,
            f"{ACCOUNTABILITY_CONTRACT_VERSION}\0{domain}\0{value}".encode(),
            "sha256",
        )
        return f"pairwise:v1:{_b64url(token[:16])}"

    def _commitment(self, domain: str, value: object) -> dict[str, str]:
        digest = hmac.new(
            self._hmac_key,
            (
                f"{ACCOUNTABILITY_CONTRACT_VERSION}\0{domain}\0".encode()
                + canonical_accountability_bytes(value)
            ),
            hashlib.sha256,
        ).hexdigest()
        return {
            "scheme": "hmac_sha256_v1",
            "purpose": PURPOSE,
            "digest": f"sha256:{digest}",
        }

    def issue(
        self,
        *,
        command: JobSearchCommandV1,
        event_id: str,
        sequence: int,
        status: ReceiptStatus,
        started_at: datetime,
        completed_at: datetime,
        result: dict[str, object] | None,
        reason_code: str | None,
    ) -> ExecutionReceiptV1:
        payload: dict[str, object] = {
            "contract_version": ACCOUNTABILITY_CONTRACT_VERSION,
            "receipt_id": self.new_opaque_id(),
            "event_id": event_id,
            "stream_pairwise_id": self._pairwise_reference(
                "stream",
                f"{command.context.tenant_id}\0{command.context.correlation_id}",
            ),
            "sequence": sequence,
            "subject_pairwise_id": self._pairwise_reference(
                "subject",
                f"{command.context.tenant_id}\0{command.actor_id}",
            ),
            "tenant_scope": self._commitment(
                "tenant_scope",
                {"tenant_id": command.context.tenant_id},
            ),
            "purpose": PURPOSE,
            "request_id": self._opaque_reference(
                "request",
                command.context.request_id,
            ),
            "idempotency_key": self._opaque_reference(
                "idempotency",
                command.idempotency_key,
            ),
            "action_commitment": self._commitment(
                "action",
                command.to_dict(),
            ),
            "execution_id": self._opaque_reference(
                "execution",
                command.context.execution_id,
            ),
            "executor_pairwise_id": self._executor_pairwise_id,
            "status": status,
            "started_at": _whole_minute(started_at),
            "completed_at": _whole_minute(completed_at),
            "result_commitment": (
                self._commitment("result", result)
                if status == "succeeded" and result is not None
                else None
            ),
            "reason_code": reason_code,
            "daml_transaction": None,
            "signature": {
                "algorithm": "ed25519",
                "key_id": self._key_id,
                "signature": "A" * 86,
            },
        }
        signing_bytes = execution_receipt_signing_bytes_v1(payload)
        signature = self._signing_key.sign(signing_bytes)
        payload["signature"]["signature"] = _b64url(signature)  # type: ignore[index]
        return ExecutionReceiptV1.from_dict(payload)


def verify_receipt_signature(
    receipt: ExecutionReceiptV1,
    public_key_bytes: bytes,
) -> None:
    """Raise InvalidSignature when a receipt is not signed by the trusted key."""
    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    signature = base64.urlsafe_b64decode(
        receipt.signature.signature + "=="
    )
    public_key.verify(
        signature,
        execution_receipt_signing_bytes_v1(receipt),
    )
