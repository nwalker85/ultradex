"""FastAPI application for Ultradex"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from contextlib import asynccontextmanager
from arq import create_pool
from strawberry.fastapi import GraphQLRouter

from core import (
    init_database,
    close_database,
    DexClient,
    ClaudeClient,
    ContactAnalyzer,
    JobSearchNATSPublisher,
    ReceiptIssuer,
    UnavailableJobSearchPublisher,
)
from . import dependencies
from .auth import (
    require_command_principal,
    require_delegation_admin_principal,
    require_read_principal,
    validate_auth_configuration,
)
from core.workers import redis_settings_from_env


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    # Startup
    database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/ultradex")
    dex_api_key = os.getenv("DEX_API_KEY")
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    validate_auth_configuration()

    if not dex_api_key or not claude_api_key:
        raise ValueError("Missing DEX_API_KEY or CLAUDE_API_KEY environment variables")

    init_database(database_url)
    redis = None
    jobsearch_publisher = None
    try:
        redis = await create_pool(redis_settings_from_env())
        receipt_issuer = ReceiptIssuer.from_env()
        nats_url = os.getenv("NATS_URL")
        if nats_url:
            candidate = JobSearchNATSPublisher(url=nats_url)
            try:
                await candidate.connect()
                jobsearch_publisher = candidate
            except Exception:
                await candidate.close()
                logger.warning(
                    "Job-search JetStream unavailable; commands will fail closed"
                )
                jobsearch_publisher = UnavailableJobSearchPublisher(
                    "NATS JetStream connection unavailable"
                )
        else:
            jobsearch_publisher = UnavailableJobSearchPublisher()
        app_state = {
            "dex": DexClient(dex_api_key),
            "claude": ClaudeClient(claude_api_key),
            "redis": redis,
            "jobsearch_publisher": jobsearch_publisher,
            "receipt_issuer": receipt_issuer,
        }
        app_state["analyzer"] = ContactAnalyzer(app_state["dex"], app_state["claude"])
        dependencies.set_app_state(app_state)
        yield
    finally:
        if jobsearch_publisher is not None:
            await jobsearch_publisher.close()
        if redis is not None:
            await redis.close()
        dependencies.set_app_state({})
        close_database()


app = FastAPI(
    title="Ultradex API",
    description="AI-powered networking relationship assistant",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["localhost", "127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routes
from .routes import contacts, analysis, health, operations
from .routes.v2 import (
    commands,
    delegations,
    jobsearch_commands,
    operations as operations_v2,
)
from .graphql.schema import get_graphql_context, schema

app.include_router(
    contacts.router,
    prefix="/api/v1",
    tags=["contacts"],
    dependencies=[Depends(require_command_principal)],
)
app.include_router(
    analysis.router,
    prefix="/api/v1",
    tags=["analysis"],
    dependencies=[Depends(require_command_principal)],
)
app.include_router(
    operations.router,
    prefix="/api/v1",
    tags=["operations"],
    dependencies=[Depends(require_read_principal)],
)
app.include_router(commands.router, prefix="/api/v2", tags=["commands"])
app.include_router(
    jobsearch_commands.router,
    prefix="/api/v2",
    tags=["job-search commands"],
)
app.include_router(
    operations_v2.router,
    prefix="/api/v2",
    tags=["operations"],
    dependencies=[Depends(require_read_principal)],
)
app.include_router(
    delegations.router,
    prefix="/api/v2",
    tags=["delegations"],
    dependencies=[Depends(require_delegation_admin_principal)],
)
app.include_router(health.router, tags=["health"])
app.include_router(
    GraphQLRouter(schema, context_getter=get_graphql_context),
    prefix="/api/graphql",
    tags=["graphql"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
