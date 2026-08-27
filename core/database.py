"""Database connection and session management."""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker
from .jobsearch_migrations import run_jobsearch_migrations
from .jobsearch_models import JOBSEARCH_VERSIONED_TABLES
from .models import (
    Base,
    get_engine,
    ContactDB,
    AnalysisRunDB,
    OperationDB,
    OperationEventDB,
    DelegationDB,
    IdempotencyKeyDB,
)

class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = get_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def init(self):
        """Initialize database tables"""
        legacy_tables = [
            table
            for table in Base.metadata.sorted_tables
            if table.name
            not in JOBSEARCH_VERSIONED_TABLES
        ]
        with self.engine.begin() as connection:
            Base.metadata.create_all(connection, tables=legacy_tables)
            run_jobsearch_migrations(
                self.database_url,
                connection=connection,
            )
    
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
    if _db is not None:
        _db.close()
    _db = Database(database_url)
    _db.init()


def close_database() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None

def get_db() -> Generator[Session, None, None]:
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized")
    session = _db.get_session()
    try:
        yield session
    finally:
        session.close()
