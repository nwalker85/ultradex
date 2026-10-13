"""Canonical Contact Identity Resolution Service for Ultradex / Career Command Center (CCC).

A human contact has a single Primary Contact ID (e.g., `contact:noah_rossi_a7f9`).
Phone numbers, email addresses, LinkedIn profile URLs, Dex IDs, and iMessage handles
are associated Identity Channel records linked to that Primary Contact ID.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    LINKEDIN = "linkedin"
    IMESSAGE = "imessage"
    DEX = "dex"
    SLACK = "slack"


class ContactRole(str, Enum):
    RECRUITER = "recruiter"
    CHAMPION = "champion"
    EXECUTIVE = "executive"
    PEER = "peer"
    PERSONAL = "personal"
    VENDOR = "vendor"


class ContactIdentityRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"ident-{uuid.uuid4().hex[:10]}")
    contact_id: str
    channel_type: ChannelType
    identity_value: str
    raw_value: str
    label: str = "primary"  # mobile, work, personal, direct
    is_primary: bool = False
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PrimaryContact(BaseModel):
    id: str
    canonical_name: str
    headline: Optional[str] = None
    organization: Optional[str] = None
    role_classification: ContactRole = ContactRole.PEER
    relationship_strength: float = 0.5  # 0.0 - 1.0
    identities: List[ContactIdentityRecord] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


ContactIdentityRecord.model_rebuild()
PrimaryContact.model_rebuild()


def normalize_phone(raw_phone: str) -> Optional[str]:
    """Normalizes phone string to standard E.164 format (+1XXXXXXXXXX)."""
    if not raw_phone:
        return None
    digits = re.sub(r"\D", "", str(raw_phone))
    if not digits:
        return None
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}" if not raw_phone.startswith("+") else f"+{digits}"


def normalize_email(raw_email: str) -> Optional[str]:
    """Normalizes email to clean lowercase format."""
    if not raw_email:
        return None
    cleaned = raw_email.strip().lower()
    # Extract email from <email@domain.com>
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", cleaned)
    return match.group(0) if match else cleaned


def normalize_linkedin_url(raw_url: str) -> Optional[str]:
    """Normalizes LinkedIn URL to standard canonical slug."""
    if not raw_url:
        return None
    cleaned = raw_url.strip().lower()
    cleaned = re.sub(r"\?.*$", "", cleaned)  # Strip query params
    cleaned = cleaned.rstrip("/")
    return cleaned


def generate_contact_slug(name: str) -> str:
    """Generates a stable deterministic slug for a contact name."""
    clean_name = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    short_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()[:6]
    return f"contact:{clean_name}_{short_hash}" if clean_name else f"contact:unknown_{short_hash}"


class InMemoryIdentityResolver:
    """Fast in-memory resolver with persistent database backing."""

    def __init__(self):
        # Index: (channel_type, normalized_value) -> contact_id
        self._identity_index: Dict[Tuple[str, str], str] = {}
        # Index: contact_id -> PrimaryContact
        self._contacts: Dict[str, PrimaryContact] = {}

    def resolve_or_create(
        self,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        dex_id: Optional[str] = None,
        organization: Optional[str] = None,
        headline: Optional[str] = None,
        role: Optional[ContactRole] = None,
    ) -> PrimaryContact:
        """Resolves an incoming entity to a single Primary Contact ID across all supplied channels."""
        norm_phone = normalize_phone(phone) if phone else None
        norm_email = normalize_email(email) if email else None
        norm_li = normalize_linkedin_url(linkedin_url) if linkedin_url else None

        # 1. Lookup existing contact across any matching channel identity
        matched_contact_id: Optional[str] = None
        if norm_phone and (ChannelType.PHONE.value, norm_phone) in self._identity_index:
            matched_contact_id = self._identity_index[(ChannelType.PHONE.value, norm_phone)]
        elif norm_email and (ChannelType.EMAIL.value, norm_email) in self._identity_index:
            matched_contact_id = self._identity_index[(ChannelType.EMAIL.value, norm_email)]
        elif norm_li and (ChannelType.LINKEDIN.value, norm_li) in self._identity_index:
            matched_contact_id = self._identity_index[(ChannelType.LINKEDIN.value, norm_li)]
        elif dex_id and (ChannelType.DEX.value, dex_id) in self._identity_index:
            matched_contact_id = self._identity_index[(ChannelType.DEX.value, dex_id)]

        # 2. If no channel identity matched, check if primary contact slug matches
        if not matched_contact_id:
            slug = generate_contact_slug(name or "Unknown")
            if slug in self._contacts:
                matched_contact_id = slug
            else:
                # Create brand new Primary Contact
                matched_contact_id = slug
                contact = PrimaryContact(
                    id=matched_contact_id,
                    canonical_name=name or "Unknown Contact",
                    headline=headline,
                    organization=organization,
                    role_classification=role or ContactRole.PEER,
                )
                self._contacts[matched_contact_id] = contact

        contact = self._contacts[matched_contact_id]

        # Update metadata if new information provided
        if name and contact.canonical_name == "Unknown Contact":
            contact.canonical_name = name
        if headline and not contact.headline:
            contact.headline = headline
        if organization and not contact.organization:
            contact.organization = organization
        if role:
            contact.role_classification = role
        contact.updated_at = datetime.now(timezone.utc)

        # 3. Associate all provided identities
        identities_to_add: List[Tuple[ChannelType, str, str]] = []
        if norm_phone:
            identities_to_add.append((ChannelType.PHONE, norm_phone, phone or ""))
        if norm_email:
            identities_to_add.append((ChannelType.EMAIL, norm_email, email or ""))
        if norm_li:
            identities_to_add.append((ChannelType.LINKEDIN, norm_li, linkedin_url or ""))
        if dex_id:
            identities_to_add.append((ChannelType.DEX, dex_id, dex_id))

        for c_type, norm_val, raw_val in identities_to_add:
            key = (c_type.value, norm_val)
            self._identity_index[key] = matched_contact_id

            # Add to contact's identity list if not already present
            if not any(i.channel_type == c_type and i.identity_value == norm_val for i in contact.identities):
                rec = ContactIdentityRecord(
                    contact_id=matched_contact_id,
                    channel_type=c_type,
                    identity_value=norm_val,
                    raw_value=raw_val,
                    is_primary=len(contact.identities) == 0,
                )
                contact.identities.append(rec)

        return contact

    def get_by_channel(self, channel_type: ChannelType, identity_value: str) -> Optional[PrimaryContact]:
        """Lookup primary contact by channel identifier."""
        norm_val = identity_value
        if channel_type == ChannelType.PHONE:
            norm_val = normalize_phone(identity_value) or identity_value
        elif channel_type == ChannelType.EMAIL:
            norm_val = normalize_email(identity_value) or identity_value
        elif channel_type == ChannelType.LINKEDIN:
            norm_val = normalize_linkedin_url(identity_value) or identity_value

        contact_id = self._identity_index.get((channel_type.value, norm_val))
        return self._contacts.get(contact_id) if contact_id else None
