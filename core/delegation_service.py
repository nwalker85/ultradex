"""Delegation-based authorization service"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from .models import DelegationDB


class DelegationService:
    @staticmethod
    def validate_delegation(
        db: Session,
        actor_id: str,
        action: str,
        delegation_id: Optional[str] = None
    ) -> bool:
        """
        Validate if actor is authorized to perform action.

        Args:
            db: Database session
            actor_id: The entity requesting authorization
            action: The action to perform (e.g., "analyze", "sync")
            delegation_id: Optional delegation ID to validate

        Returns:
            True if authorized, False otherwise
        """
        query = db.query(DelegationDB).filter(
            DelegationDB.delegatee == actor_id,
            DelegationDB.expires_at > datetime.now(),
            DelegationDB.revoked_at.is_(None)
        )

        if delegation_id:
            query = query.filter(DelegationDB.id == delegation_id)

        delegation = query.first()
        if not delegation:
            return False

        # Check if action is allowed
        allowed_actions = delegation.allowed_actions or []
        return action in allowed_actions or "*" in allowed_actions

    @staticmethod
    def create_delegation(
        db: Session,
        delegator: str,
        delegatee: str,
        allowed_actions: list,
        allowed_resources: list = None,
        days_valid: int = 30
    ) -> DelegationDB:
        """Create a new delegation"""
        delegation = DelegationDB(
            delegator=delegator,
            delegatee=delegatee,
            allowed_actions=allowed_actions,
            allowed_resources=allowed_resources or ["*"],
            expires_at=datetime.now() + timedelta(days=days_valid)
        )
        db.add(delegation)
        db.commit()
        db.refresh(delegation)
        return delegation

    @staticmethod
    def revoke_delegation(db: Session, delegation_id: str) -> bool:
        """Revoke a delegation"""
        delegation = db.query(DelegationDB).filter(
            DelegationDB.id == delegation_id
        ).first()
        if delegation:
            delegation.revoked_at = datetime.now()
            db.commit()
            return True
        return False

    @staticmethod
    def get_delegation(db: Session, delegation_id: str) -> Optional[DelegationDB]:
        """Get delegation by ID"""
        return db.query(DelegationDB).filter(
            DelegationDB.id == delegation_id
        ).first()
