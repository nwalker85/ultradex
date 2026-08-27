"""CRUD for operator entity notes (non-event-sourced annotations)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .jobsearch_models import ENTITY_NOTE_TYPES, EntityNoteDB


@dataclass(frozen=True)
class EntityNote:
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

    @classmethod
    def from_row(cls, row: EntityNoteDB) -> EntityNote:
        return cls(
            note_id=row.id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            submitted_by=row.submitted_by,
            category=row.category,
            disposition=row.disposition,
            assigned_to=row.assigned_to,
            comment=row.comment,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def list_entity_notes(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 50,
) -> list[EntityNote]:
    if entity_type not in ENTITY_NOTE_TYPES:
        raise ValueError(f"unsupported entity_type: {entity_type}")
    rows = (
        db.query(EntityNoteDB)
        .filter_by(entity_type=entity_type, entity_id=entity_id)
        .order_by(EntityNoteDB.created_at.desc())
        .limit(limit)
        .all()
    )
    return [EntityNote.from_row(row) for row in rows]


def create_entity_note(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    submitted_by: str,
    comment: str,
    category: str | None = None,
    disposition: str | None = None,
    assigned_to: str | None = None,
) -> EntityNote:
    if entity_type not in ENTITY_NOTE_TYPES:
        raise ValueError(f"unsupported entity_type: {entity_type}")
    text = comment.strip()
    if not text:
        raise ValueError("comment is required")
    now = datetime.now(timezone.utc)
    row = EntityNoteDB(
        id=f"note-{uuid.uuid4()}",
        entity_type=entity_type,
        entity_id=entity_id,
        submitted_by=submitted_by,
        category=category.strip() if category else None,
        disposition=disposition.strip() if disposition else None,
        assigned_to=assigned_to.strip() if assigned_to else None,
        comment=text,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return EntityNote.from_row(row)
