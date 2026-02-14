"""Database connection and session management"""

from sqlalchemy.orm import Session
from .models import get_engine, get_session_factory, init_db, ContactDB, AnalysisRunDB

class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = get_engine(database_url)
        self.SessionLocal = get_session_factory(database_url)
    
    def init(self):
        """Initialize database tables"""
        init_db(self.database_url)
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connections"""
        self.engine.dispose()


# Dependency for FastAPI
_db = None

def init_database(database_url: str):
    global _db
    _db = Database(database_url)
    _db.init()

def get_db() -> Database:
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db
