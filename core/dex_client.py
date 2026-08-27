"""Client for Dex REST API"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, List, Optional

import httpx
from sqlalchemy.orm import Session

from .models import ContactBase, ContactDB


class DexClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # api.getdex.com lost its SNI mapping on Google's ghs frontend
        # (2026-08-14, dead globally); Dex's current API lives on
        # api.prod.getdex.com/v1 with Bearer auth.
        self.base_url = "https://api.prod.getdex.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    async def fetch_all_contacts(self) -> List[ContactBase]:
        """Fetch all contacts from Dex with cursor pagination.

        /v1 ignores limit/offset/page entirely (verified 2026-08-14: every
        combination returns the same 500-item first page) and paginates only
        via data.nextCursor. Offset-style looping therefore never terminates
        — both guards below fail loudly rather than spin.
        """
        contacts = []
        seen_ids = set()
        cursor = None
        max_pages = 100  # 50k contacts; far above the ~2.2k expected

        async with httpx.AsyncClient(timeout=30) as client:
            for _ in range(max_pages):
                params = {"cursor": cursor} if cursor else {}
                response = await client.get(
                    f"{self.base_url}/contacts", params=params, headers=self.headers
                )
                response.raise_for_status()

                data = response.json()
                # /v1 envelope: {"error": false, "data": {"items": [...], "nextCursor": ...}}
                # (the legacy /api/rest surface returned {"data": [...]}).
                payload = data.get("data", {})
                batch = payload.get("items", []) if isinstance(payload, dict) else payload

                new_items = [c for c in batch if c.get("id") not in seen_ids]
                if batch and not new_items:
                    raise RuntimeError(
                        "Dex /v1 returned an already-seen page: cursor param not "
                        "honored; aborting instead of looping"
                    )

                for contact_data in new_items:
                    seen_ids.add(contact_data.get("id"))
                    contact = self._parse_contact(contact_data)
                    if contact:
                        contacts.append(contact)

                cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
                if not cursor or not batch:
                    break
            else:
                raise RuntimeError(
                    f"Dex pagination exceeded {max_pages} pages; refusing to continue"
                )

        return contacts

    async def fetch_contact_raw(self, contact_id: str) -> dict[str, Any] | None:
        """Fetch raw Dex contact payload (LinkedIn message metadata lives here)."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/contacts/{contact_id}",
                headers=self.headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json().get("data")
            return payload if isinstance(payload, dict) else None

    def fetch_contact_raw_sync(self, contact_id: str) -> dict[str, Any] | None:
        """Sync Dex contact fetch for use inside FastAPI/GraphQL sync resolvers."""
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{self.base_url}/contacts/{contact_id}",
                headers=self.headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json().get("data")
            return payload if isinstance(payload, dict) else None
    
    async def write_note(self, contact_id: str, note_content: str) -> bool:
        """Write analysis note to contact's timeline"""
        url = f"{self.base_url}/timeline_items"
        
        payload = {
            "contact_id": contact_id,
            "body": f"[AI Analysis] {note_content}",
            "created_at": datetime.now().isoformat()
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=self.headers)
            return response.status_code in (200, 201)
    
    def _parse_contact(self, data: dict) -> Optional[ContactBase]:
        """Parse Dex API response into ContactBase"""
        try:
            return ContactBase(
                id=data.get("id"),
                name=self._get_full_name(data),
                email=self._get_primary_email(data),
                company=data.get("company") or data.get("company_name"),
                job_title=data.get("job_title") or data.get("headline"),
                phone=self._get_primary_phone(data),
                notes=data.get("notes") or data.get("description"),
            )
        except Exception as e:
            print(f"Error parsing contact {data.get('id')}: {e}")
            return None
    
    def _get_full_name(self, data: dict) -> str:
        # /v1 sends explicit nulls, so .get(key, "") still yields None.
        first = (data.get("first_name") or "").strip()
        last = (data.get("last_name") or "").strip()
        name = f"{first} {last}".strip()
        return name or "Unknown"
    
    def _get_primary_email(self, data: dict) -> Optional[str]:
        emails = data.get("emails", [])
        if emails and isinstance(emails, list):
            return emails[0].get("email") if isinstance(emails[0], dict) else emails[0]
        return None
    
    def _get_primary_phone(self, data: dict) -> Optional[str]:
        phones = data.get("phone_numbers", [])
        if phones and isinstance(phones, list):
            return phones[0].get("phone_number") if isinstance(phones[0], dict) else phones[0]
        return None


def _linkedin_profile_url(dex_data: dict[str, Any]) -> str | None:
    handle = (dex_data.get("linkedin") or "").strip()
    if not handle:
        return None
    if handle.startswith("http://") or handle.startswith("https://"):
        return handle
    return f"https://www.linkedin.com/in/{handle.removeprefix('@')}"


def _dex_channel_entry(
    *,
    contact_id: str,
    channel: str,
    prefix: str,
    snippet: str | None,
    occurred_at: str | None,
    thread_link: str | None,
    subject: str,
) -> dict[str, Any] | None:
    if not snippet and not occurred_at and not thread_link:
        return None
    return {
        "id": f"dex-{prefix}-{contact_id}",
        "timestamp": occurred_at or datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "direction": "inbound",
        "subject": subject,
        "summary": (snippet or "Open thread in Dex to view the latest message.")[:500],
        "message_id": None,
        "evidence_ref": None,
        "thread_id": thread_link,
    }


def communication_entries_from_dex(
    contact_id: str,
    dex_data: dict[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for prefix, channel, subject in (
        ("linkedin", "linkedin", "LinkedIn conversation"),
        ("whatsapp", "dex", "WhatsApp conversation"),
        ("imessage", "dex", "iMessage conversation"),
        ("instagram", "dex", "Instagram conversation"),
    ):
        entry = _dex_channel_entry(
            contact_id=contact_id,
            channel=channel,
            prefix=prefix,
            snippet=dex_data.get(f"{prefix}_last_message_snippet"),
            occurred_at=dex_data.get(f"{prefix}_last_message_at"),
            thread_link=dex_data.get(f"{prefix}_message_link"),
            subject=subject,
        )
        if entry is not None:
            entries.append(entry)
    return entries


def merge_communication_history(
    existing: list[dict[str, Any]] | None,
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = {item["id"]: item for item in (existing or []) if item.get("id")}
    for entry in incoming:
        merged[entry["id"]] = entry
    return sorted(
        merged.values(),
        key=lambda item: item.get("timestamp") or "",
        reverse=True,
    )


def apply_dex_enrichment(row: ContactDB, dex_data: dict[str, Any]) -> bool:
    changed = False
    linkedin_url = _linkedin_profile_url(dex_data)
    if linkedin_url and row.linkedin_url != linkedin_url:
        row.linkedin_url = linkedin_url
        changed = True

    incoming = communication_entries_from_dex(row.id, dex_data)
    if not incoming:
        return changed

    merged = merge_communication_history(row.communication_history, incoming)
    if merged != (row.communication_history or []):
        row.communication_history = merged
        changed = True
        latest = merged[0].get("timestamp")
        if latest:
            try:
                parsed = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    parsed = parsed.replace(tzinfo=None)
                if row.last_contacted is None or parsed > row.last_contacted:
                    row.last_contacted = parsed
                    changed = True
            except ValueError:
                pass
    return changed


def enrich_contact_from_dex(db: Session, contact_id: str) -> ContactDB | None:
    """Lazy Dex refresh — merges LinkedIn/messaging snippets into communication_history."""
    api_key = os.getenv("DEX_API_KEY", "").strip()
    row = db.get(ContactDB, contact_id)
    if row is None:
        return None
    if not api_key:
        return row

    dex_data = DexClient(api_key).fetch_contact_raw_sync(contact_id)
    if not dex_data:
        return row

    if apply_dex_enrichment(row, dex_data):
        db.commit()
        db.refresh(row)
    return row
