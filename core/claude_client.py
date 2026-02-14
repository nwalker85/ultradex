"""Client for Claude API via Anthropic"""

import httpx
import json
from typing import Optional
from .models import ContactAnalysis, ContactBase


class ClaudeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.model = "claude-3-5-sonnet-20241022"
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
    
    async def analyze_contact(self, contact: ContactBase, days_since_contact: Optional[int] = None) -> Optional[ContactAnalysis]:
        """Analyze a single contact using Claude"""
        prompt = self._build_prompt(contact, days_since_contact)
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "max_tokens": 500,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                content = data["content"][0]["text"]
                
                return self._parse_analysis(content)
        except Exception as e:
            print(f"Error analyzing contact {contact.id}: {e}")
            return None
    
    def _build_prompt(self, contact: ContactBase, days_since_contact: Optional[int]) -> str:
        """Build analysis prompt for Claude"""
        return f"""Analyze this professional contact and score their networking value on a scale of 0-100.

Contact Information:
- Name: {contact.name}
- Company: {contact.company or "Unknown"}
- Job Title: {contact.job_title or "Unknown"}
- Email: {contact.email or "Not provided"}
- Days Since Last Contact: {days_since_contact or "Unknown"}
- Notes: {contact.notes or "None"}

Evaluate based on:
- Professional influence and seniority
- Mutual benefit potential
- Relationship strength from notes
- Industry relevance (tech, AI, business)

Respond ONLY with valid JSON (no markdown, no extra text):
{{
    "value_score": <0-100 number>,
    "reason": "<2-3 sentence explanation>",
    "outreach_strategy": "<specific, personalized strategy>",
    "suggested_timing": "<'This week', 'Within 2 weeks', 'Next month'>"
}}"""
    
    def _parse_analysis(self, response_text: str) -> Optional[ContactAnalysis]:
        """Parse Claude's JSON response"""
        try:
            # Clean up response
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            data = json.loads(text)
            
            return ContactAnalysis(
                value_score=float(data["value_score"]),
                reason=data["reason"],
                outreach_strategy=data["outreach_strategy"],
                suggested_timing=data["suggested_timing"]
            )
        except Exception as e:
            print(f"Error parsing Claude response: {e}")
            print(f"Raw response: {response_text}")
            return None
