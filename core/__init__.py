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
from .jobsearch_migrations import alembic_config, run_jobsearch_migrations
from .jobsearch_models import (
    JOBSEARCH_COMMAND_TABLES,
    JOBSEARCH_PROJECTION_TABLES,
    JOBSEARCH_PROJECTION_TYPES,
    ApplicationProjectionDB,
    OpportunityProjectionDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
    JobSearchApprovalDB,
    JobSearchCommandDB,
    JobSearchEvidenceReferenceDB,
    JobSearchExecutionReceiptDB,
    JobSearchLifecycleEventDB,
)
from .jobsearch_projections import (
    JobSearchProjectionRepository,
    ProjectedOutreach,
    ProjectionPage,
)
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
from .jobsearch_commands import (
    JobSearchCommandRequest,
    JobSearchDispatchError,
    JobSearchGatewayService,
)
from .jobsearch_nats import (
    COMMAND_SUBJECTS,
    JobSearchNATSPublisher,
    JobSearchTaskPublisher,
    UnavailableJobSearchPublisher,
)
from .jobsearch_receipts import ReceiptIssuer, verify_receipt_signature
from .jobsearch_executors import (
    DomainRefusal,
    EvidenceIngestResult,
    JobSearchExecutionOutcome,
    JobSearchExecutor,
    OpportunityScoreResult,
    RelationshipSyncResult,
    RetryableCommandError,
)
from .jobsearch_worker import (
    JobSearchPullConsumer,
    JobSearchWorker,
    run_jobsearch_worker,
)

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
    "JOBSEARCH_PROJECTION_TABLES",
    "JOBSEARCH_COMMAND_TABLES",
    "JOBSEARCH_PROJECTION_TYPES",
    "OpportunityProjectionDB",
    "ApplicationProjectionDB",
    "RelationshipProjectionDB",
    "OutreachProjectionDB",
    "ProjectionCheckpointDB",
    "JobSearchCommandDB",
    "JobSearchEvidenceReferenceDB",
    "JobSearchApprovalDB",
    "JobSearchLifecycleEventDB",
    "JobSearchExecutionReceiptDB",
    "JobSearchProjectionRepository",
    "ProjectedOutreach",
    "ProjectionPage",
    "alembic_config",
    "run_jobsearch_migrations",
    "JobSearchCommandRequest",
    "JobSearchDispatchError",
    "JobSearchGatewayService",
    "COMMAND_SUBJECTS",
    "JobSearchNATSPublisher",
    "JobSearchTaskPublisher",
    "UnavailableJobSearchPublisher",
    "ReceiptIssuer",
    "verify_receipt_signature",
    "DomainRefusal",
    "EvidenceIngestResult",
    "JobSearchExecutionOutcome",
    "JobSearchExecutor",
    "OpportunityScoreResult",
    "RelationshipSyncResult",
    "RetryableCommandError",
    "JobSearchWorker",
    "JobSearchPullConsumer",
    "run_jobsearch_worker",
]
