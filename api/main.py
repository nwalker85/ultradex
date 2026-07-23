"""FastAPI application for Ultradex"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager
from arq import create_pool
from arq.connections import RedisSettings
from strawberry.fastapi import GraphQLRouter

from core import (
    init_database,
    DexClient,
    ClaudeClient,
    ContactAnalyzer,
)
from . import dependencies


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    # Startup
    database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/ultradex")
    dex_api_key = os.getenv("DEX_API_KEY")
    claude_api_key = os.getenv("CLAUDE_API_KEY")

    if not dex_api_key or not claude_api_key:
        raise ValueError("Missing DEX_API_KEY or CLAUDE_API_KEY environment variables")

    init_database(database_url)

    # Parse Redis URL
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    # Initialize Redis
    redis = await create_pool(
        RedisSettings(host=redis_host, port=redis_port, database=0)
    )

    app_state = {
        "dex": DexClient(dex_api_key),
        "claude": ClaudeClient(claude_api_key),
        "redis": redis,
    }
    app_state["analyzer"] = ContactAnalyzer(app_state["dex"], app_state["claude"])

    # Register app state with dependencies module
    dependencies.set_app_state(app_state)

    yield

    # Cleanup
    await redis.close()


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
from .routes.v2 import commands, operations as operations_v2, delegations
from .graphql.schema import get_graphql_context, schema

app.include_router(contacts.router, prefix="/api/v1", tags=["contacts"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
app.include_router(operations.router, prefix="/api/v1", tags=["operations"])
app.include_router(commands.router, prefix="/api/v2", tags=["commands"])
app.include_router(operations_v2.router, prefix="/api/v2", tags=["operations"])
app.include_router(delegations.router, prefix="/api/v2", tags=["delegations"])
app.include_router(health.router, tags=["health"])
app.include_router(
    GraphQLRouter(schema, context_getter=get_graphql_context),
    prefix="/api/graphql",
    tags=["graphql"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
