"""HTTP client for communicating with Ultradex API"""

import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime


class UltradexAPIClient:
    """Client for the internal Ultradex FastAPI service"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60)
    
    async def sync_contacts(self) -> Dict[str, Any]:
        """Sync all contacts from Dex to local database"""
        response = await self.client.post("/api/v1/contacts/sync")
        response.raise_for_status()
        return response.json()
    
    async def analyze_contacts(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run AI analysis on contacts"""
        params = {}
        if limit is not None:
            params["limit"] = limit
        
        response = await self.client.post("/api/v1/analyze", params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_contacts(self) -> List[Dict[str, Any]]:
        """Get all cached contacts"""
        response = await self.client.get("/api/v1/contacts")
        response.raise_for_status()
        return response.json()
    
    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """Get a specific contact"""
        response = await self.client.get(f"/api/v1/contacts/{contact_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_neglected_contacts(self) -> List[Dict[str, Any]]:
        """Get neglected contacts (value ≥60, days ≥30)"""
        response = await self.client.get("/api/v1/contacts/neglected/list")
        response.raise_for_status()
        return response.json()
    
    async def add_note_to_contact(self, contact_id: str, note: str) -> Dict[str, Any]:
        """Write a note to a contact in Dex"""
        response = await self.client.post(
            f"/api/v1/contacts/{contact_id}/note",
            json={"content": note}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_analysis_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent analysis runs"""
        response = await self.client.get("/api/v1/analyze/runs", params={"limit": limit})
        response.raise_for_status()
        return response.json()
    
    async def get_analysis_stats(self) -> Dict[str, Any]:
        """Get aggregate analysis statistics"""
        response = await self.client.get("/api/v1/stats")
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        response = await self.client.get("/health")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
