"""Delegation management endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from core import (
    get_db,
    DelegationService,
    DelegationResponse,
    DelegationDB,
)

router = APIRouter()


@router.post("/delegations", response_model=DelegationResponse)
async def create_delegation(
    delegator: str,
    delegatee: str,
    allowed_actions: List[str],
    allowed_resources: List[str] = None,
    days_valid: int = 30,
    db: Session = Depends(get_db)
):
    """Create a new delegation"""
    try:
        if not allowed_resources:
            allowed_resources = ["*"]

        delegation = DelegationService.create_delegation(
            db,
            delegator=delegator,
            delegatee=delegatee,
            allowed_actions=allowed_actions,
            allowed_resources=allowed_resources,
            days_valid=days_valid
        )

        return DelegationResponse(
            id=delegation.id,
            delegator=delegation.delegator,
            delegatee=delegation.delegatee,
            allowed_actions=delegation.allowed_actions,
            allowed_resources=delegation.allowed_resources,
            expires_at=delegation.expires_at,
            revoked_at=delegation.revoked_at,
            created_at=delegation.created_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating delegation: {str(e)}")


@router.get("/delegations", response_model=List[DelegationResponse])
async def list_delegations(
    delegatee: str = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """List delegations"""
    try:
        query = db.query(DelegationDB).filter(
            DelegationDB.revoked_at.is_(None),
            DelegationDB.expires_at > datetime.now()
        )

        if delegatee:
            query = query.filter(DelegationDB.delegatee == delegatee)

        delegations = query.limit(limit).all()

        return [
            DelegationResponse(
                id=d.id,
                delegator=d.delegator,
                delegatee=d.delegatee,
                allowed_actions=d.allowed_actions,
                allowed_resources=d.allowed_resources,
                expires_at=d.expires_at,
                revoked_at=d.revoked_at,
                created_at=d.created_at
            )
            for d in delegations
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching delegations: {str(e)}")


@router.delete("/delegations/{delegation_id}")
async def revoke_delegation(
    delegation_id: str,
    db: Session = Depends(get_db)
):
    """Revoke a delegation"""
    try:
        success = DelegationService.revoke_delegation(db, delegation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Delegation not found")

        return {"status": "revoked", "delegation_id": delegation_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error revoking delegation: {str(e)}")
