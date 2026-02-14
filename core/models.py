"""Data models for Hrafngrima using Pydantic and SQLAlchemy"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Float, DateTime, Integer, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Pydantic models (API/SDK)

class ContactBase(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class ContactAnalysis(BaseModel):
    value_score: float  # 0-100
    reason: str
    outreach_strategy: str
    suggested_timing: str


class ContactWithAnalysis(ContactBase):
    last_contacted: Optional[datetime] = None
    ai_value: Optional[float] = None
    ai_reason: Optional[str] = None
    outreach_strategy: Optional[str] = None
    last_analyzed: Optional[datetime] = None
    
    @property
    def days_since_contact(self) -> Optional[int]:
        if not self.last_contacted:
            return None
        return (datetime.now() - self.last_contacted).days
    
    @property
    def is_neglected(self) -> bool:
        if self.ai_value is None or self.days_since_contact is None:
            return False
        return self.ai_value >= 60 and self.days_since_contact >= 30


class AnalysisRunResponse(BaseModel):
    timestamp: datetime
    contacts_analyzed: int
    neglected_contacts_found: int
    estimated_tokens: int
    estimated_cost: float
    success: bool
    error_message: Optional[str] = None


# SQLAlchemy models (Database)

Base = declarative_base()


class ContactDB(Base):
    __tablename__ = "contacts"
    
    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    last_contacted = Column(DateTime, nullable=True)
    
    # AI analysis fields
    ai_value = Column(Float, nullable=True)
    ai_reason = Column(Text, nullable=True)
    outreach_strategy = Column(Text, nullable=True)
    suggested_timing = Column(String(255), nullable=True)
    last_analyzed = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    synced_at = Column(DateTime, default=datetime.now)


class AnalysisRunDB(Base):
    __tablename__ = "analysis_runs"
    
    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    contacts_analyzed = Column(Integer, default=0)
    neglected_contacts_found = Column(Integer, default=0)
    estimated_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    success = Column(Integer, default=1)  # Boolean as int
    error_message = Column(Text, nullable=True)


class SettingsDB(Base):
    __tablename__ = "settings"
    
    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# Database setup
def get_engine(database_url: str):
    return create_engine(database_url)


def get_session_factory(database_url: str):
    engine = get_engine(database_url)
    return sessionmaker(bind=engine)


def init_db(database_url: str):
    """Create all tables"""
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
