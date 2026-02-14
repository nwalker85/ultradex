"""MCP Server for Hrafngrima - exposes contact analysis tools to Jarvis"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent, ToolResult

from .client import HrafngrimaAPIClient
from .tools import TOOLS

logger = logging.getLogger(__name__)


class HrafngrimaMCPServer:
    """MCP server exposing Hrafngrima tools for Jarvis integration"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.server = Server("hrafngrima")
        self.api_client = HrafngrimaAPIClient(api_base_url)
        self._register_tools()
    
    def _register_tools(self):
        """Register MCP tools with the server"""
        for tool_def in TOOLS:
            @self.server.call_tool()
            async def handle_tool_call(name: str = tool_def["name"], arguments: Dict[str, Any] = None):
                return await self._execute_tool(name, arguments or {})
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result"""
        try:
            if tool_name == "hrafngrima/sync_contacts":
                result = await self._sync_contacts()
            elif tool_name == "hrafngrima/analyze_contacts":
                result = await self._analyze_contacts(arguments.get("limit"))
            elif tool_name == "hrafngrima/get_contacts":
                result = await self._get_contacts()
            elif tool_name == "hrafngrima/get_contact":
                result = await self._get_contact(arguments["contact_id"])
            elif tool_name == "hrafngrima/get_neglected_contacts":
                result = await self._get_neglected_contacts()
            elif tool_name == "hrafngrima/write_note":
                result = await self._write_note(arguments["contact_id"], arguments["note"])
            elif tool_name == "hrafngrima/get_analysis_stats":
                result = await self._get_analysis_stats()
            elif tool_name == "hrafngrima/get_analysis_history":
                result = await self._get_analysis_history(arguments.get("limit", 10))
            else:
                return ToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {tool_name}")],
                    is_error=True
                )
            
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(result, indent=2, default=str))],
                is_error=False
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                is_error=True
            )
    
    async def _sync_contacts(self) -> Dict[str, Any]:
        """Sync contacts from Dex"""
        logger.info("Syncing contacts from Dex...")
        result = await self.api_client.sync_contacts()
        logger.info(f"Synced {result.get('contacts_synced', 0)} contacts")
        return {
            "success": True,
            "message": f"Synced {result.get('contacts_synced', 0)} contacts from Dex",
            "data": result
        }
    
    async def _analyze_contacts(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run analysis on contacts"""
        logger.info(f"Running analysis (limit={limit})...")
        result = await self.api_client.analyze_contacts(limit)
        logger.info(
            f"Analysis complete: {result.get('analyzed')} analyzed, "
            f"{result.get('neglected')} neglected found"
        )
        return {
            "success": True,
            "message": (
                f"Analysis complete: {result.get('analyzed')} contacts analyzed, "
                f"{result.get('neglected')} neglected contacts found"
            ),
            "data": result
        }
    
    async def _get_contacts(self) -> Dict[str, Any]:
        """Get all contacts"""
        logger.info("Fetching all contacts...")
        contacts = await self.api_client.get_contacts()
        logger.info(f"Found {len(contacts)} contacts")
        return {
            "success": True,
            "count": len(contacts),
            "contacts": contacts
        }
    
    async def _get_contact(self, contact_id: str) -> Dict[str, Any]:
        """Get a specific contact"""
        logger.info(f"Fetching contact {contact_id}...")
        contact = await self.api_client.get_contact(contact_id)
        return {
            "success": True,
            "contact": contact
        }
    
    async def _get_neglected_contacts(self) -> Dict[str, Any]:
        """Get neglected contacts"""
        logger.info("Fetching neglected contacts...")
        contacts = await self.api_client.get_neglected_contacts()
        logger.info(f"Found {len(contacts)} neglected contacts")
        return {
            "success": True,
            "count": len(contacts),
            "neglected_contacts": contacts
        }
    
    async def _write_note(self, contact_id: str, note: str) -> Dict[str, Any]:
        """Write a note to a contact"""
        logger.info(f"Writing note to contact {contact_id}...")
        result = await self.api_client.add_note_to_contact(contact_id, note)
        logger.info(f"Note written successfully")
        return {
            "success": True,
            "message": f"Note written to contact {contact_id}",
            "data": result
        }
    
    async def _get_analysis_stats(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        logger.info("Fetching analysis statistics...")
        stats = await self.api_client.get_analysis_stats()
        return {
            "success": True,
            "stats": stats
        }
    
    async def _get_analysis_history(self, limit: int = 10) -> Dict[str, Any]:
        """Get analysis run history"""
        logger.info(f"Fetching analysis history (limit={limit})...")
        runs = await self.api_client.get_analysis_runs(limit)
        logger.info(f"Found {len(runs)} analysis runs")
        return {
            "success": True,
            "count": len(runs),
            "runs": runs
        }
    
    async def start(self, stdio: bool = True):
        """Start the MCP server
        
        Args:
            stdio: If True, use stdio for transport. If False, use other transport.
        """
        logger.info(f"Starting Hrafngrima MCP server (API: {self.api_base_url})...")
        
        # Check API health before starting
        try:
            health = await self.api_client.health_check()
            logger.info(f"API health check: {health}")
        except Exception as e:
            logger.warning(f"API health check failed: {e}")
        
        if stdio:
            import sys
            await self.server.run(sys.stdin, sys.stdout)
        else:
            # For non-stdio transport, return server for custom handling
            return self.server
    
    async def close(self):
        """Close the server and cleanup"""
        await self.api_client.close()
        logger.info("Hrafngrima MCP server closed")
