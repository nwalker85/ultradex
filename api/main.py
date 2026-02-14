"""FastAPI application for Hrafngrima"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager

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
    database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/hrafngrima")
    dex_api_key = os.getenv("DEX_API_KEY")
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    
    if not dex_api_key or not claude_api_key:
        raise ValueError("Missing DEX_API_KEY or CLAUDE_API_KEY environment variables")
    
    init_database(database_url)
    
    app_state = {
        "dex": DexClient(dex_api_key),
        "claude": ClaudeClient(claude_api_key),
    }
    app_state["analyzer"] = ContactAnalyzer(app_state["dex"], app_state["claude"])
    
    # Register app state with dependencies module
    dependencies.set_app_state(app_state)
    
    yield
    
    # Cleanup
    pass


app = FastAPI(
    title="Hrafngrima API",
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
from .routes import contacts, analysis, health

app.include_router(contacts.router, prefix="/api/v1", tags=["contacts"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
app.include_router(health.router, tags=["health"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
