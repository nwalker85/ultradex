"""Client for Dex REST API"""

import httpx
import os
from urllib.parse import urlencode
from typing import List, Optional
from datetime import datetime, timezone
from .models import ContactBase


class DexClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = os.getenv("DEX_API_BASE_URL", "https://api.prod.getdex.com").rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    async def fetch_all_contacts(self) -> List[ContactBase]:
        """Fetch all contacts from Dex with pagination"""
        contacts = []
        take = 100
        cursor: str | None = None
        seen_cursors: set[str] = set()
        
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params = {"take": str(take)}
                if cursor:
                    params["cursor"] = cursor
                url = f"{self.base_url}/v1/contacts?{urlencode(params)}"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                envelope = data.get("data", data)
                batch = (
                    envelope.get("items", [])
                    if isinstance(envelope, dict)
                    else envelope
                )
                
                for contact_data in batch:
                    contact = self._parse_contact(contact_data)
                    if contact:
                        contacts.append(contact)
                
                if not isinstance(envelope, dict):
                    break
                next_cursor = envelope.get("nextCursor")
                if not isinstance(next_cursor, str) or not next_cursor:
                    break
                if next_cursor in seen_cursors:
                    raise RuntimeError("Dex pagination returned a duplicate cursor")
                seen_cursors.add(next_cursor)
                cursor = next_cursor
        
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
                notes=data.get("notes"),
                last_contacted=self._get_last_contacted(data),
            )
        except Exception as e:
            print(f"Error parsing contact {data.get('id')}: {e}")
            return None
    
    def _get_full_name(self, data: dict) -> str:
        full_name = (data.get("full_name") or "").strip()
        if full_name:
            return full_name
        first = data.get("first_name", "").strip()
        last = data.get("last_name", "").strip()
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

    def _get_last_contacted(self, data: dict) -> Optional[datetime]:
        candidates = [
            data.get("gcal_last_interaction_at"),
            data.get("gmail_last_interaction_at"),
            data.get("imessage_last_message_at"),
            data.get("linkedin_last_message_at"),
            data.get("phone_call_last_interaction_at"),
            data.get("whatsapp_last_message_at"),
            data.get("instagram_last_message_at"),
            data.get("first_interaction_at"),
            data.get("last_seen_at"),
        ]
        parsed = [
            value
            for raw in candidates
            if raw
            for value in (self._parse_timestamp(str(raw)),)
            if value is not None
        ]
        return max(parsed) if parsed else None

    def _parse_timestamp(self, value: str) -> Optional[datetime]:
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            return None
