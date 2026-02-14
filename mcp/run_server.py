#!/usr/bin/env python
"""Entrypoint for running the Hrafngrima MCP server"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import HrafngrimaMCPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]  # Log to stderr, stdout is reserved for MCP protocol
)

logger = logging.getLogger(__name__)


async def main():
    """Run the MCP server"""
    # Get API base URL from environment or use default
    api_base_url = os.getenv("HRAFNGRIMA_API_URL", "http://localhost:8000")
    
    logger.info(f"Initializing Hrafngrima MCP server")
    logger.info(f"API URL: {api_base_url}")
    
    server = HrafngrimaMCPServer(api_base_url=api_base_url)
    
    try:
        await server.start(stdio=True)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())
