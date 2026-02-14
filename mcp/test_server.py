#!/usr/bin/env python
"""Tests for Hrafngrima MCP server"""

import asyncio
import json
from typing import Any, Dict

from client import HrafngrimaAPIClient


async def test_api_client():
    """Test the API client methods"""
    print("Testing Hrafngrima API Client...\n")
    
    async with HrafngrimaAPIClient() as client:
        # Test health check
        print("1. Testing health check...")
        try:
            health = await client.health_check()
            print(f"   ✓ API is healthy: {health}\n")
        except Exception as e:
            print(f"   ✗ Health check failed: {e}\n")
            return False
        
        # Test get contacts
        print("2. Testing get_contacts...")
        try:
            contacts = await client.get_contacts()
            print(f"   ✓ Got {len(contacts)} contacts\n")
        except Exception as e:
            print(f"   ✗ Failed to get contacts: {e}\n")
            return False
        
        # Test get analysis runs
        print("3. Testing get_analysis_runs...")
        try:
            runs = await client.get_analysis_runs(limit=5)
            print(f"   ✓ Got {len(runs)} analysis runs\n")
        except Exception as e:
            print(f"   ✗ Failed to get analysis runs: {e}\n")
            return False
        
        # Test get analysis stats
        print("4. Testing get_analysis_stats...")
        try:
            stats = await client.get_analysis_stats()
            print(f"   ✓ Stats: {json.dumps(stats, indent=2, default=str)}\n")
        except Exception as e:
            print(f"   ✗ Failed to get stats: {e}\n")
            return False
    
    print("All API client tests passed! ✓\n")
    return True


async def test_mcp_server_tools():
    """Test MCP server tool definitions"""
    print("Testing MCP Server Tool Definitions...\n")
    
    from tools import TOOLS
    
    print(f"Found {len(TOOLS)} tools:\n")
    for tool in TOOLS:
        print(f"  • {tool['name']}")
        print(f"    {tool['description']}\n")
    
    # Verify all tools have required fields
    required_fields = {"name", "description", "inputSchema"}
    for tool in TOOLS:
        missing = required_fields - set(tool.keys())
        if missing:
            print(f"  ✗ Tool {tool.get('name')} missing fields: {missing}")
            return False
    
    print("All tools properly defined! ✓\n")
    return True


async def test_mcp_server_init():
    """Test MCP server initialization"""
    print("Testing MCP Server Initialization...\n")
    
    try:
        from server import HrafngrimaMCPServer
        
        server = HrafngrimaMCPServer(api_base_url="http://localhost:8000")
        print(f"  ✓ Server initialized successfully\n")
        
        # Check health
        try:
            health = await server.api_client.health_check()
            print(f"  ✓ API connectivity confirmed\n")
        except Exception as e:
            print(f"  ⚠ API not accessible: {e}")
            print(f"    (This is expected if Hrafngrima API isn't running)\n")
        
        await server.close()
        return True
    except Exception as e:
        print(f"  ✗ Server initialization failed: {e}\n")
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Hrafngrima MCP Server Test Suite")
    print("=" * 60 + "\n")
    
    results = {
        "API Client": await test_api_client(),
        "Tool Definitions": await test_mcp_server_tools(),
        "Server Init": await test_mcp_server_init(),
    }
    
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    all_passed = all(results.values())
    print("=" * 60)
    print(f"Overall: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
