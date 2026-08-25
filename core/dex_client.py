"""Client for Dex REST API"""

import httpx
from typing import List, Optional
from datetime import datetime
from .models import ContactBase


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
