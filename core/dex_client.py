"""Client for Dex REST API"""

import httpx
from typing import List, Optional
from datetime import datetime
from .models import ContactBase


class DexClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.getdex.com/api/rest"
        self.headers = {
            "x-hasura-dex-api-key": api_key,
            "Content-Type": "application/json",
        }
    
    async def fetch_all_contacts(self) -> List[ContactBase]:
        """Fetch all contacts from Dex with pagination"""
        contacts = []
        offset = 0
        limit = 100
        
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                url = f"{self.base_url}/contacts?limit={limit}&offset={offset}"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                batch = data.get("data", [])
                
                for contact_data in batch:
                    contact = self._parse_contact(contact_data)
                    if contact:
                        contacts.append(contact)
                
                if len(batch) < limit:
                    break
                
                offset += limit
        
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
                company=data.get("company_name"),
                job_title=data.get("headline"),
                phone=self._get_primary_phone(data),
                notes=data.get("notes"),
            )
        except Exception as e:
            print(f"Error parsing contact {data.get('id')}: {e}")
            return None
    
    def _get_full_name(self, data: dict) -> str:
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
