# Hrafngrima MCP Integration with Jarvis

Guide for integrating Hrafngrima MCP server with Jarvis (The Viking voice AI agent).

## Quick Start

### 1. Copy MCP Server to Jarvis

```bash
# Assuming Jarvis is at ~/src/products/theviking/jarvis/

# Copy Hrafngrima MCP files
cp -r ~/src/products/hrafngrima/mcp ~/src/products/theviking/jarvis/mcp-servers/hrafngrima

# Or create a symlink for development
ln -s ~/src/products/hrafngrima/mcp ~/src/products/theviking/jarvis/mcp-servers/hrafngrima
```

### 2. Configure Jarvis

Update Jarvis FastAPI configuration to include Hrafngrima MCP server:

**File:** `~/src/products/theviking/jarvis/api/config.py` or equivalent

```python
MCP_SERVERS = {
    "hrafngrima": {
        "type": "stdio",
        "command": "python",
        "args": [
            "/path/to/hrafngrima/mcp/run_server.py"
        ],
        "env": {
            "HRAFNGRIMA_API_URL": "http://localhost:8000",
            "PYTHONUNBUFFERED": "1"
        },
        "timeout": 30,
    }
}
```

Or using environment variables:

```python
import os

MCP_SERVERS = {
    "hrafngrima": {
        "type": "stdio",
        "command": "python",
        "args": [os.getenv("HRAFNGRIMA_MCP_PATH", "/path/to/hrafngrima/mcp/run_server.py")],
        "env": {
            "HRAFNGRIMA_API_URL": os.getenv("HRAFNGRIMA_API_URL", "http://localhost:8000"),
            "PYTHONUNBUFFERED": "1"
        },
    }
}
```

### 3. Start Jarvis with Hrafngrima

```bash
# Make sure Hrafngrima API is running
cd ~/src/products/hrafngrima
docker-compose up -d

# Start Jarvis
cd ~/src/products/theviking/jarvis
uvicorn api.main:app --reload
```

### 4. Test Integration

Test that Jarvis can call Hrafngrima tools:

```bash
# Via curl
curl -X POST http://localhost:8000/jarvis/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "server": "hrafngrima",
    "tool": "hrafngrima/get_contacts",
    "arguments": {}
  }'

# Or via Python client
import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/jarvis/mcp/call",
            json={
                "server": "hrafngrima",
                "tool": "hrafngrima/get_neglected_contacts",
                "arguments": {}
            }
        )
        print(response.json())

asyncio.run(test())
```

## Voice Commands for Jarvis

Once integrated, Jarvis can respond to voice commands:

### Sync Contacts
> "Sync my contacts from Dex"

```
Jarvis: "Syncing 247 contacts from Dex... Done! All contacts are up to date."
```

### Check Neglected Contacts
> "Who have I neglected recently?"

```
Jarvis: "You have 8 high-value contacts you haven't reached out to in 30+ days. 
Jane Smith at Acme Corp - you should reconnect about LLM optimization.
..."
```

### Run Analysis
> "Analyze my contact relationships"

```
Jarvis: "Running analysis... Complete! I found 8 neglected high-value contacts 
out of 45 analyzed. The analysis took 2.5 minutes and cost $0.68 in API calls."
```

### Get Specific Contact
> "Tell me about Jane Smith"

```
Jarvis: "Jane Smith - VP Engineering at Acme Corp. Value Score: 82/100. 
You last contacted her on December 15th - 61 days ago. 
I recommend reaching out this week with an article on token optimization."
```

### Write a Note
> "Note that I talked to Jane about the new AI framework"

```
Jarvis: "I've written a note to Jane's profile in Dex: 'Discussed the new 
AI framework and multi-agent systems. Interest in LLM optimization tools.'"
```

## Architecture

```
┌─────────────────────────────────────────┐
│  Voice Input                            │
│  (User speaks to Jarvis)                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Jarvis FastAPI Server                  │
│  - Speech Recognition                   │
│  - Intent Classification                │
│  - Agent Reasoning                      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  MCP Manager       │
         │  (in Jarvis)       │
         └────────┬───────────┘
                  │
          ┌───────┴───────┐
          ▼               ▼
  ┌──────────────┐  ┌──────────────────┐
  │ Other MCPs   │  │ Hrafngrima MCP   │
  └──────────────┘  │ - sync_contacts  │
                    │ - analyze        │
                    │ - get_neglected  │
                    │ - write_note     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Hrafngrima API   │
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
                ┌────────┐        ┌──────────┐
                │ Dex    │        │ Claude   │
                └────────┘        │ (Analysis)
                                  └──────────┘
```

## Error Handling

If the Hrafngrima MCP server fails to start:

```
Jarvis: "The contact management system is currently unavailable. 
The Hrafngrima API may not be running. Please check that:
1. The Hrafngrima API server is running (docker-compose up)
2. It's accessible at the configured URL (http://localhost:8000)
3. Your API keys (DEX_API_KEY, CLAUDE_API_KEY) are configured correctly"
```

## Monitoring

### Check MCP Server Logs

```bash
# View Hrafngrima MCP logs
docker logs hrafngrima-api 2>&1 | grep -i mcp

# Or check Jarvis logs for MCP errors
docker logs jarvis-api 2>&1 | grep -E "(hrafngrima|MCP|ERROR)"
```

### Health Checks

```bash
# Check Hrafngrima API
curl http://localhost:8000/health
# Expected: {"status":"ok","timestamp":"..."}

# Check Jarvis MCP connectivity
curl http://localhost:8001/health/mcp
# (If Jarvis exposes this endpoint)
```

## Development

### Testing MCP Server Standalone

```bash
# Terminal 1: Start Hrafngrima API
cd ~/src/products/hrafngrima
docker-compose up

# Terminal 2: Test MCP server
cd ~/src/products/hrafngrima
python mcp/test_server.py

# Terminal 3: Run MCP server directly
python mcp/run_server.py
```

### Adding New Tools

To add new tools to Hrafngrima that Jarvis can use:

1. Add endpoint to FastAPI API (`api/routes/`)
2. Add tool definition to `mcp/tools.py`
3. Add handler method to `mcp/server.py`
4. Update documentation
5. Restart Jarvis

Example:

```python
# 1. API endpoint (api/routes/contacts.py)
@router.post("/contacts/send-email")
async def send_email(contact_id: str, subject: str, body: str):
    # Implementation
    pass

# 2. Tool definition (mcp/tools.py)
{
    "name": "hrafngrima/send_email",
    "description": "Send an email to a contact...",
    "inputSchema": { ... }
}

# 3. Handler (mcp/server.py)
async def _send_email(self, contact_id: str, subject: str, body: str):
    result = await self.api_client.send_email(contact_id, subject, body)
    return { "success": True, "data": result }
```

## Performance Considerations

### Timeouts

- Default API timeout: 60 seconds
- If analysis takes >60s, increase in `mcp/client.py`:

```python
self.client = httpx.AsyncClient(
    base_url=self.base_url,
    timeout=120  # Increase to 2 minutes
)
```

### Rate Limiting

- Dex API: 100 contacts per request (handles pagination)
- Claude API: 1 request/second (built-in delay in analyzer)
- Jarvis MCP: No rate limiting (adjust if needed)

### Caching

Consider caching in Jarvis to reduce API calls:

```python
# Cache contacts for 1 hour
@cache(ttl=3600)
async def get_contacts():
    return await mcp.call_tool("hrafngrima/get_contacts")
```

## Troubleshooting

### MCP Server Won't Start

```bash
# Check Python version
python --version  # Need 3.11+

# Check dependencies
pip list | grep mcp

# Check Hrafngrima API is running
curl http://localhost:8000/health

# Run with debug
PYTHONUNBUFFERED=1 python mcp/run_server.py 2>&1
```

### Jarvis Can't Call Tools

```bash
# Check MCP server configuration in Jarvis
grep -r "hrafngrima" ~/src/products/theviking/jarvis/

# Verify MCP server path
ls -la /path/to/hrafngrima/mcp/run_server.py

# Test MCP directly
python mcp/test_server.py
```

### Slow Responses

```bash
# Check API performance
time curl http://localhost:8000/api/v1/contacts

# Check Claude API latency
# (See Hrafngrima logs for API call times)

# Consider using limit parameter for analysis
curl -X POST http://localhost:8000/api/v1/analyze?limit=10
```

## Future Enhancements

- [ ] Real-time contact sync subscriptions
- [ ] Voice-based contact creation/editing
- [ ] Smart scheduling (best time to reach out)
- [ ] Sentiment analysis of past interactions
- [ ] Predictive relationship health scoring
- [ ] Integration with calendar for meeting tracking
- [ ] Slack/email inbox integration
