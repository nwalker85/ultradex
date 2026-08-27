"""Operator entity notes — list and create annotations on CRM records."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import AuthenticatedPrincipal, require_command_principal, require_read_principal
from core import get_db
from core.entity_notes import create_entity_note, list_entity_notes
from core.jobsearch_models import ENTITY_NOTE_TYPES

router = APIRouter()


class EntityNoteResponse(BaseModel):
    note_id: str
    entity_type: str
    entity_id: str
    submitted_by: str
    category: str | None
    disposition: str | None
    assigned_to: str | None
    comment: str
    created_at: datetime
    updated_at: datetime


class CreateEntityNoteRequest(BaseModel):
    entity_type: str = Field(..., description="contact|organization|relationship|opportunity|application|lead")
    entity_id: str
    comment: str = Field(..., min_length=1, max_length=8000)
    category: str | None = Field(default=None, max_length=128)
    disposition: str | None = Field(default=None, max_length=128)
    assigned_to: str | None = Field(default=None, max_length=255)


def _to_response(note) -> EntityNoteResponse:
    return EntityNoteResponse(
        note_id=note.note_id,
        entity_type=note.entity_type,
        entity_id=note.entity_id,
        submitted_by=note.submitted_by,
        category=note.category,
        disposition=note.disposition,
        assigned_to=note.assigned_to,
        comment=note.comment,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get("/entity-notes", response_model=list[EntityNoteResponse])
async def get_entity_notes(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _principal: AuthenticatedPrincipal = Depends(require_read_principal),
) -> list[EntityNoteResponse]:
    if entity_type not in ENTITY_NOTE_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported entity_type: {entity_type}")
    notes = list_entity_notes(db, entity_type=entity_type, entity_id=entity_id, limit=limit)
    return [_to_response(note) for note in notes]


@router.post("/entity-notes", response_model=EntityNoteResponse, status_code=201)
async def post_entity_note(
    body: CreateEntityNoteRequest,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_command_principal),
) -> EntityNoteResponse:
    if body.entity_type not in ENTITY_NOTE_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported entity_type: {body.entity_type}")
    try:
        note = create_entity_note(
            db,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            submitted_by=principal.subject,
            comment=body.comment,
            category=body.category,
            disposition=body.disposition,
            assigned_to=body.assigned_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(note)
