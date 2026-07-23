"""Idempotency key management service"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from .models import EventType, IdempotencyKeyDB, OperationEventDB


class IdempotencyService:
    @staticmethod
    def claim_key(
        db: Session,
        key: str,
        operation_id: str,
        ttl_hours: int = 24,
    ) -> bool:
        """Atomically claim a new or expired key inside the caller transaction."""
        now = datetime.now()
        values = {
            "key": key,
            "operation_id": operation_id,
            "created_at": now,
            "expires_at": now + timedelta(hours=ttl_hours),
        }
        dialect = db.get_bind().dialect.name
        if dialect == "sqlite":
            statement = sqlite_insert(IdempotencyKeyDB).values(**values)
        elif dialect == "postgresql":
            statement = postgresql_insert(IdempotencyKeyDB).values(**values)
        else:  # pragma: no cover - supported deployments are PostgreSQL/SQLite
            raise RuntimeError(f"Unsupported idempotency dialect: {dialect}")
        statement = statement.on_conflict_do_update(
            index_elements=[IdempotencyKeyDB.key],
            set_={
                "operation_id": operation_id,
                "created_at": now,
                "expires_at": values["expires_at"],
            },
            where=IdempotencyKeyDB.expires_at <= now,
        )
        result = db.execute(statement)
        return result.rowcount == 1

    @staticmethod
    def get_cached_operation(db: Session, key: str) -> Optional[str]:
        """
        Get cached operation_id for an idempotency key.

        Returns:
            operation_id if key exists and not expired, None otherwise
        """
        idempotency = db.query(IdempotencyKeyDB).filter(
            IdempotencyKeyDB.key == key,
            IdempotencyKeyDB.expires_at > datetime.now()
        ).first()

        if idempotency:
            return idempotency.operation_id
        return None

    @staticmethod
    def get_cached_binding(
        db: Session,
        key: str,
    ) -> Optional[tuple[str, str]]:
        """Return the operation and immutable request fingerprint for a live key."""
        operation_id = IdempotencyService.get_cached_operation(db, key)
        if operation_id is None:
            return None
        accepted = (
            db.query(OperationEventDB)
            .filter(
                OperationEventDB.operation_id == operation_id,
                OperationEventDB.event_type == EventType.OPERATION_ACCEPTED,
            )
            .order_by(OperationEventDB.id.asc())
            .first()
        )
        fingerprint = (accepted.payload or {}).get("idempotency_fingerprint") if accepted else None
        if not isinstance(fingerprint, str) or not fingerprint:
            return operation_id, "legacy-unbound"
        return operation_id, fingerprint

    @staticmethod
    def cleanup_expired_keys(db: Session) -> int:
        """
        Delete expired idempotency keys.

        Returns:
            Number of keys deleted
        """
        expired = db.query(IdempotencyKeyDB).filter(
            IdempotencyKeyDB.expires_at <= datetime.now()
        ).delete()
        db.commit()
        return expired
