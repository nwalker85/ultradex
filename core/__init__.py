"""Ultradex core business logic"""

from .models import (
    ContactBase,
    ContactAnalysis,
    ContactWithAnalysis,
    AnalysisRunResponse,
    ContactDB,
    AnalysisRunDB,
    init_db,
    get_engine,
    get_session_factory,
    OperationDB,
    OperationStatus,
    OperationResponse,
    OperationEventDB,
    EventType,
    OperationEvent,
    DelegationDB,
    DelegationResponse,
    IdempotencyKeyDB,
)
from .database import Database, close_database, init_database, get_db
from .dex_client import DexClient
from .claude_client import ClaudeClient
from .contact_analyzer import ContactAnalyzer
from .operation_service import OperationService
from .gateway import (
    CommandRequest,
    GatewayService,
    IdempotencyConflictError,
    QueueDispatchError,
)
from .event_producer import EventProducer
from .delegation_service import DelegationService
from .idempotency_service import IdempotencyService

__all__ = [
    "ContactBase",
    "ContactAnalysis",
    "ContactWithAnalysis",
    "AnalysisRunResponse",
    "ContactDB",
    "AnalysisRunDB",
    "OperationDB",
    "OperationStatus",
    "OperationResponse",
    "OperationEventDB",
    "EventType",
    "OperationEvent",
    "Database",
    "init_database",
    "close_database",
    "get_db",
    "DexClient",
    "ClaudeClient",
    "ContactAnalyzer",
    "OperationService",
    "GatewayService",
    "CommandRequest",
    "IdempotencyConflictError",
    "QueueDispatchError",
    "EventProducer",
    "DelegationService",
    "IdempotencyService",
]
