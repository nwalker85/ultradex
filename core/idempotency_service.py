"""Idempotency key management service"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from .models import IdempotencyKeyDB


class IdempotencyService:
    @staticmethod
    def record_key(
        db: Session,
        key: str,
        operation_id: str,
        ttl_hours: int = 24
    ) -> IdempotencyKeyDB:
        """
        Record an idempotency key mapping to operation_id.

        Args:
            db: Database session
            key: The idempotency key (unique)
            operation_id: The operation this key belongs to
            ttl_hours: Time to live in hours
        """
        idempotency = IdempotencyKeyDB(
            key=key,
            operation_id=operation_id,
            expires_at=datetime.now() + timedelta(hours=ttl_hours)
        )
        db.add(idempotency)
        db.commit()
        db.refresh(idempotency)
        return idempotency

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
