"""Contact management endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from core import (
    ContactBase,
    ContactWithAnalysis,
    ContactDB,
    get_db,
    DexClient,
    ContactAnalyzer,
)
from ..dependencies import get_dex_client, get_analyzer

router = APIRouter()


@router.get("/contacts", response_model=List[ContactWithAnalysis])
async def list_contacts(db: Session = Depends(get_db)):
    """Get all cached contacts from database"""
    try:
        contacts = db.query(ContactDB).all()
        return [
            ContactWithAnalysis(
                id=c.id,
                name=c.name,
                email=c.email,
                company=c.company,
                job_title=c.job_title,
                phone=c.phone,
                notes=c.notes,
                last_contacted=c.last_contacted,
                ai_value=c.ai_value,
                ai_reason=c.ai_reason,
                outreach_strategy=c.outreach_strategy,
                suggested_timing=c.suggested_timing,
                last_analyzed=c.last_analyzed,
            )
            for c in contacts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching contacts: {str(e)}")


@router.get("/contacts/{contact_id}", response_model=ContactWithAnalysis)
async def get_contact(contact_id: str, db: Session = Depends(get_db)):
    """Get a specific contact by ID"""
    try:
        contact = db.query(ContactDB).filter(ContactDB.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        return ContactWithAnalysis(
            id=contact.id,
            name=contact.name,
            email=contact.email,
            company=contact.company,
            job_title=contact.job_title,
            phone=contact.phone,
            notes=contact.notes,
            last_contacted=contact.last_contacted,
            ai_value=contact.ai_value,
            ai_reason=contact.ai_reason,
            outreach_strategy=contact.outreach_strategy,
            suggested_timing=contact.suggested_timing,
            last_analyzed=contact.last_analyzed,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching contact: {str(e)}")


@router.get("/contacts/neglected/list", response_model=List[ContactWithAnalysis])
async def get_neglected_contacts(
    analyzer: ContactAnalyzer = Depends(get_analyzer),
    db: Session = Depends(get_db)
):
    """Get all neglected contacts (value >= 60, days since contact >= 30)"""
    try:
        neglected = analyzer.get_neglected_contacts(db)
        return neglected
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching neglected contacts: {str(e)}")


@router.post("/contacts/sync")
async def sync_contacts(
    analyzer: ContactAnalyzer = Depends(get_analyzer),
    db: Session = Depends(get_db)
):
    """Sync all contacts from Dex to local database"""
    try:
        count = await analyzer.sync_contacts(db)
        return {
            "status": "success",
            "contacts_synced": count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing contacts: {str(e)}")


@router.post("/contacts/{contact_id}/note")
async def add_note_to_contact(
    contact_id: str,
    note: dict,
    dex: DexClient = Depends(get_dex_client),
    db: Session = Depends(get_db)
):
    """Write a note to a contact in Dex"""
    try:
        contact = db.query(ContactDB).filter(ContactDB.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        content = note.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Note content is required")
        
        success = await dex.write_note(contact_id, content)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to write note to Dex")
        
        return {
            "status": "success",
            "contact_id": contact_id,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding note: {str(e)}")
