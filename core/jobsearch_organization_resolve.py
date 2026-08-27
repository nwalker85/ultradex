"""Resolve employer strings to organization directory rows."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .jobsearch_models import OrganizationDB


def _normalize_employer(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def find_organization_for_employer(
    session: Session,
    employer_name: str,
    *,
    organization_id: str | None = None,
) -> OrganizationDB | None:
    """Return an organization row when id or employer name matches."""
    if organization_id:
        row = session.get(OrganizationDB, organization_id.strip())
        if row is not None:
            return row

    employer = (employer_name or "").strip()
    if not employer:
        return None

    normalized = _normalize_employer(employer)
    row = session.scalar(
        select(OrganizationDB).where(
            func.lower(func.trim(OrganizationDB.name)) == normalized
        )
    )
    if row is not None:
        return row

    for candidate in session.scalars(select(OrganizationDB)):
        if _normalize_employer(candidate.name) == normalized:
            return candidate
    return None


def resolve_organization_id(
    session: Session,
    employer_name: str,
    *,
    organization_id: str | None = None,
) -> str | None:
    row = find_organization_for_employer(
        session,
        employer_name,
        organization_id=organization_id,
    )
    return row.id if row is not None else None
