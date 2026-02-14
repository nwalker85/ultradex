"""Core business logic for contact analysis and scoring"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from .models import ContactBase, ContactWithAnalysis, ContactAnalysis, AnalysisRunDB, ContactDB
from .dex_client import DexClient
from .claude_client import ClaudeClient


class ContactAnalyzer:
    def __init__(self, dex_client: DexClient, claude_client: ClaudeClient):
        self.dex = dex_client
        self.claude = claude_client
    
    async def sync_contacts(self, db_session: Session) -> int:
        """Sync all contacts from Dex to database"""
        try:
            contacts = await self.dex.fetch_all_contacts()
            
            for contact in contacts:
                existing = db_session.query(ContactDB).filter(
                    ContactDB.id == contact.id
                ).first()
                
                if existing:
                    # Update
                    existing.name = contact.name
                    existing.email = contact.email
                    existing.company = contact.company
                    existing.job_title = contact.job_title
                    existing.phone = contact.phone
                    existing.notes = contact.notes
                    existing.updated_at = datetime.now()
                    existing.synced_at = datetime.now()
                else:
                    # Create
                    db_contact = ContactDB(
                        id=contact.id,
                        name=contact.name,
                        email=contact.email,
                        company=contact.company,
                        job_title=contact.job_title,
                        phone=contact.phone,
                        notes=contact.notes,
                        synced_at=datetime.now()
                    )
                    db_session.add(db_contact)
            
            db_session.commit()
            return len(contacts)
        except Exception as e:
            db_session.rollback()
            print(f"Error syncing contacts: {e}")
            raise
    
    async def analyze_contacts(self, db_session: Session, limit: Optional[int] = None) -> dict:
        """Analyze contacts that need analysis"""
        # Get contacts needing analysis (never analyzed or stale)
        query = db_session.query(ContactDB).filter(
            (ContactDB.last_analyzed == None) |
            ((datetime.now() - ContactDB.last_analyzed).days > 7)
        )
        
        if limit:
            contacts_to_analyze = query.limit(limit).all()
        else:
            contacts_to_analyze = query.all()
        
        analyzed = 0
        neglected_count = 0
        total_tokens = 0
        
        # Analyze with rate limiting (1 sec delay)
        for i, db_contact in enumerate(contacts_to_analyze):
            contact = ContactBase(**{
                'id': db_contact.id,
                'name': db_contact.name,
                'email': db_contact.email,
                'company': db_contact.company,
                'job_title': db_contact.job_title,
                'phone': db_contact.phone,
                'notes': db_contact.notes,
            })
            
            # Calculate days since contact
            days_since = None
            if db_contact.last_contacted:
                days_since = (datetime.now() - db_contact.last_contacted).days
            
            analysis = await self.claude.analyze_contact(contact, days_since)
            
            if analysis:
                db_contact.ai_value = analysis.value_score
                db_contact.ai_reason = analysis.reason
                db_contact.outreach_strategy = analysis.outreach_strategy
                db_contact.suggested_timing = analysis.suggested_timing
                db_contact.last_analyzed = datetime.now()
                
                analyzed += 1
                total_tokens += 500  # Estimate
                
                # Check if neglected
                if analysis.value_score >= 60 and days_since and days_since >= 30:
                    neglected_count += 1
                    
                    # Write note back to Dex
                    note_content = f"""**AI Relationship Analysis:**
Value Score: {int(analysis.value_score)}/100
Reason: {analysis.reason}

**Recommended Outreach:**
{analysis.outreach_strategy}

**Suggested Timing:** {analysis.suggested_timing}"""
                    
                    asyncio.create_task(self.dex.write_note(contact.id, note_content))
            
            # Rate limiting
            if i < len(contacts_to_analyze) - 1:
                await asyncio.sleep(1)
        
        db_session.commit()
        
        # Record analysis run
        run = AnalysisRunDB(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            contacts_analyzed=analyzed,
            neglected_contacts_found=neglected_count,
            estimated_tokens=total_tokens,
            estimated_cost=total_tokens * 0.00003,
            success=1,
            error_message=None
        )
        db_session.add(run)
        db_session.commit()
        
        return {
            "analyzed": analyzed,
            "neglected": neglected_count,
            "tokens": total_tokens,
            "cost": total_tokens * 0.00003
        }
    
    def get_neglected_contacts(self, db_session: Session) -> List[ContactWithAnalysis]:
        """Get all neglected contacts (value >= 60, days >= 30)"""
        neglected = db_session.query(ContactDB).filter(
            (ContactDB.ai_value >= 60) &
            (ContactDB.last_analyzed != None)
        ).all()
        
        result = []
        for contact in neglected:
            days_since = None
            if contact.last_contacted:
                days_since = (datetime.now() - contact.last_contacted).days
            
            if days_since and days_since >= 30:
                with_analysis = ContactWithAnalysis(
                    id=contact.id,
                    name=contact.name,
                    email=contact.email,
                    company=contact.company,
                    job_title=contact.job_title,
                    phone=contact.phone,
                    notes=contact.notes,
                    last_contacted=contact.last_contacted,
                    ai_value=contact.ai_value,
                    ai_reason=contact.ai_reason,
                    outreach_strategy=contact.outreach_strategy,
                    last_analyzed=contact.last_analyzed
                )
                result.append(with_analysis)
        
        return result
