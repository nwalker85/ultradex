# Hrafngrima MCP Server

Model Context Protocol (MCP) server that exposes Hrafngrima contact analysis tools to AI agents like Jarvis.

## Overview

The MCP server acts as a bridge between AI agents (e.g., Jarvis voice AI) and the Hrafngrima API. It implements the Model Context Protocol to allow Jarvis to:

- Sync contacts from Dex
- Run AI analysis to identify high-value neglected relationships
- Query contacts and analysis results
- Write notes back to Dex

## Architecture

```
Jarvis (Voice AI)
      │
      ├─ MCP Protocol (stdio/HTTP)
      │
Hrafngrima MCP Server
      │
      ├─ HTTP Calls
      │
Hrafngrima FastAPI (Internal)
      │
      ├─ Dex API ─────┐
      │               ├─ PostgreSQL
      └─ Claude API ──┘
```

## Installation

### Requirements

- Python 3.11+
- Hrafngrima API running (http://localhost:8000 by default)

### Setup

```bash
# Install MCP library
pip install mcp

# Or add to requirements.txt
echo "mcp==0.1.0" >> ../requirements.txt
```

## Usage

### Standalone Server

```bash
# Run the MCP server with default settings
python mcp/run_server.py

# Run with custom API URL
HRAFNGRIMA_API_URL=http://api.example.com:8000 python mcp/run_server.py
```

### Jarvis Integration

Configure Jarvis to use the Hrafngrima MCP server by updating its MCP server configuration:

```python
# In Jarvis configuration
mcp_servers = {
    "hrafngrima": {
        "type": "stdio",
        "command": "python",
        "args": ["/path/to/hrafngrima/mcp/run_server.py"],
        "env": {
            "HRAFNGRIMA_API_URL": "http://localhost:8000"
        }
    }
}
```

Or using the mcp.json configuration file:

```bash
# Copy mcp.json to Jarvis MCP servers directory
cp mcp/mcp.json /path/to/jarvis/mcp-servers/hrafngrima.json

# Update path variable
sed -i 's|${HRAFNGRIMA_ROOT}|/path/to/hrafngrima|g' /path/to/jarvis/mcp-servers/hrafngrima.json
```

## Available Tools

### hrafngrima/sync_contacts

Sync all contacts from Dex to the local database.

**Parameters:** None

**Example Response:**
```json
{
  "success": true,
  "message": "Synced 247 contacts from Dex",
  "data": {
    "status": "success",
    "contacts_synced": 247,
    "timestamp": "2026-02-14T10:30:00"
  }
}
```

### hrafngrima/analyze_contacts

Run AI analysis on contacts to identify high-value relationships and generate outreach strategies.

**Parameters:**
- `limit` (integer, optional): Maximum number of contacts to analyze

**Example Response:**
```json
{
  "success": true,
  "message": "Analysis complete: 45 contacts analyzed, 8 neglected contacts found",
  "data": {
    "analyzed": 45,
    "neglected": 8,
    "tokens": 22500,
    "cost": 0.675
  }
}
```

### hrafngrima/get_contacts

Get all cached contacts from the database.

**Parameters:** None

**Example Response:**
```json
{
  "success": true,
  "count": 247,
  "contacts": [
    {
      "id": "dex-123",
      "name": "Jane Smith",
      "email": "jane@company.com",
      "company": "Acme Corp",
      "job_title": "VP Engineering",
      "ai_value": 82,
      "ai_reason": "Senior tech leader at growth-stage AI company",
      "outreach_strategy": "Share article on LLM optimization",
      "last_analyzed": "2026-02-14T08:00:00"
    }
  ]
}
```

### hrafngrima/get_contact

Get detailed information about a specific contact.

**Parameters:**
- `contact_id` (string, required): The Dex contact ID

**Example Response:**
```json
{
  "success": true,
  "contact": {
    "id": "dex-123",
    "name": "Jane Smith",
    "email": "jane@company.com",
    "company": "Acme Corp",
    "job_title": "VP Engineering",
    "phone": "+1-555-0100",
    "notes": "Met at AI conference 2025. Interested in agent frameworks.",
    "last_contacted": "2025-12-15",
    "ai_value": 82,
    "ai_reason": "Senior tech leader at growth-stage AI company. Strong mutual interest in LLM applications.",
    "outreach_strategy": "Share recent article on token optimization. Reference previous conversation about multi-agent systems.",
    "suggested_timing": "This week",
    "last_analyzed": "2026-02-14T08:00:00"
  }
}
```

### hrafngrima/get_neglected_contacts

Get high-value contacts that haven't been contacted recently.

**Criteria:**
- Value score ≥ 60
- Days since last contact ≥ 30

**Parameters:** None

**Example Response:**
```json
{
  "success": true,
  "count": 8,
  "neglected_contacts": [
    {
      "id": "dex-123",
      "name": "Jane Smith",
      "company": "Acme Corp",
      "job_title": "VP Engineering",
      "ai_value": 82,
      "ai_reason": "Senior tech leader at growth-stage AI company",
      "outreach_strategy": "Share article on LLM optimization",
      "suggested_timing": "This week",
      "last_contacted": "2025-12-15",
      "days_since_contact": 61
    }
  ]
}
```

### hrafngrima/write_note

Write a note to a contact in Dex (appended to contact's timeline).

**Parameters:**
- `contact_id` (string, required): The Dex contact ID
- `note` (string, required): The note content

**Example Response:**
```json
{
  "success": true,
  "message": "Note written to contact dex-123",
  "data": {
    "status": "success",
    "contact_id": "dex-123",
    "timestamp": "2026-02-14T10:45:00"
  }
}
```

### hrafngrima/get_analysis_stats

Get aggregate statistics about contact analysis.

**Parameters:** None

**Example Response:**
```json
{
  "success": true,
  "stats": {
    "total_runs": 4,
    "total_contacts_analyzed": 156,
    "total_neglected_found": 18,
    "total_cost": 4.68,
    "average_cost_per_run": 1.17,
    "timestamp": "2026-02-14T10:50:00"
  }
}
```

### hrafngrima/get_analysis_history

Get recent analysis runs.

**Parameters:**
- `limit` (integer, optional): Maximum number of runs to return. Defaults to 10.

**Example Response:**
```json
{
  "success": true,
  "count": 4,
  "runs": [
    {
      "id": "run-abc123",
      "timestamp": "2026-02-14T08:00:00",
      "contacts_analyzed": 45,
      "neglected_contacts_found": 8,
      "estimated_tokens": 22500,
      "estimated_cost": 0.675,
      "success": 1,
      "error_message": null
    }
  ]
}
```

## Error Handling

All tools return error responses in this format:

```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

Common error scenarios:
- **400 Bad Request**: Missing required parameters or invalid input
- **404 Not Found**: Contact or analysis run not found
- **500 Internal Error**: API error or database issue
- **Connection Error**: Hrafngrima API not accessible

## Environment Variables

- `HRAFNGRIMA_API_URL` - Base URL for Hrafngrima API (default: `http://localhost:8000`)
- `PYTHONUNBUFFERED` - Set to `1` for unbuffered output (recommended)

## Debugging

### Enable Debug Logging

```bash
# Set Python logging level
PYTHONUNBUFFERED=1 python -u mcp/run_server.py 2>&1 | grep -E "(DEBUG|ERROR|INFO)"
```

### Check API Connectivity

```bash
# Test API connection
curl http://localhost:8000/health

# Check specific endpoint
curl http://localhost:8000/api/v1/contacts
```

### View MCP Protocol Messages

```bash
# Run server with debug output
python mcp/run_server.py 2> debug.log
```

## Integration Examples

### Jarvis Voice Command

When Jarvis receives a voice command like:
> "Tell me about my neglected contacts"

It can call:
```python
result = await jarvis_mcp.call_tool(
    "hrafngrima/get_neglected_contacts",
    {}
)
```

### Periodic Analysis

Jarvis can periodically check for neglected contacts:

```python
# Every day at 9 AM
schedule.daily(jarvis_mcp.call_tool, "hrafngrima/analyze_contacts", {"limit": 50})

# If neglected contacts found, write note
result = await jarvis_mcp.call_tool("hrafngrima/get_analysis_stats", {})
if result["stats"]["total_neglected_found"] > 0:
    # Notify user via voice
    jarvis.speak("You have {} neglected contacts to reach out to".format(
        result["stats"]["total_neglected_found"]
    ))
```

## Testing

### Test MCP Server Locally

```bash
# Start Hrafngrima API
cd ~/src/products/hrafngrima
docker-compose up

# In another terminal, test MCP server
python -m pytest mcp/tests/ -v

# Or run server manually
python mcp/run_server.py
```

### Test with Claude (for development)

```bash
# Using Claude's test client
from mcp.client import Client

async with Client(subprocess.Popen(
    ["python", "mcp/run_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)) as client:
    result = await client.call_tool("hrafngrima/get_contacts", {})
    print(result)
```

## Performance

- **Sync contacts**: ~500ms (Dex API call + DB write)
- **Analyze contacts**: ~1-2s per contact (rate limited to 1 call/sec)
- **Get contacts**: ~50-100ms
- **Get neglected**: ~30-50ms

For 200 contacts:
- Full sync + analysis: ~200 seconds (~3.3 minutes)
- Just get neglected: <100ms

## Troubleshooting

### MCP Server won't start
- Check API is running: `curl http://localhost:8000/health`
- Check Python version: `python --version` (need 3.11+)
- Check MCP library installed: `pip list | grep mcp`

### Tools not appearing in Jarvis
- Verify mcp.json path is correct
- Check Jarvis MCP configuration
- Restart Jarvis after configuration changes

### API calls timing out
- Check network connectivity to Hrafngrima API
- Increase timeout in `client.py` if needed (default 60s)
- Check API logs for errors

### Analysis too slow
- Use `limit` parameter to analyze fewer contacts
- Check Claude API rate limits
- Consider running analysis during off-peak hours

## Future Enhancements

- [ ] WebSocket transport for real-time updates
- [ ] Caching layer for frequently accessed data
- [ ] Batch operations for efficiency
- [ ] Custom filtering and search tools
- [ ] Export tools (CSV, PDF)
- [ ] Notification/alert tools
- [ ] Integration with calendar systems
