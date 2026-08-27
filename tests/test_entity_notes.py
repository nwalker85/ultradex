import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.entity_notes import create_entity_note, list_entity_notes
from core.jobsearch_migrations import run_jobsearch_migrations


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notes.db'}")
    run_jobsearch_migrations(str(engine.url))
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_create_and_list_entity_notes(db_session):
    note = create_entity_note(
        db_session,
        entity_type="relationship",
        entity_id="relationship-abc",
        submitted_by="operator-1",
        comment="Follow up after intro call.",
        category="follow-up",
    )
    assert note.note_id.startswith("note-")
    assert note.submitted_by == "operator-1"
    assert note.category == "follow-up"

    notes = list_entity_notes(
        db_session,
        entity_type="relationship",
        entity_id="relationship-abc",
    )
    assert len(notes) == 1
    assert notes[0].comment == "Follow up after intro call."


def test_rejects_empty_comment(db_session):
    with pytest.raises(ValueError, match="comment"):
        create_entity_note(
            db_session,
            entity_type="contact",
            entity_id="contact-1",
            submitted_by="operator-1",
            comment="   ",
        )
