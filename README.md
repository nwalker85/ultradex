# Ultradex - AI-Powered Networking Relationship Assistant

A Python/FastAPI backend service that identifies high-value professional contacts you've neglected and provides AI-generated outreach strategies.

## Architecture

```
┌─────────────────────────────────────────┐
│  Consumers (SDK/CLI/MCP)                │
│  - Python SDK                           │
│  - Go CLI                               │
│  - MCP Server (Jarvis integration)      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  FastAPI HTTP API (Internal)            │
│  - /api/v1/contacts/*                   │
│  - /api/v1/analyze*                     │
│  - /health*                             │
└─────────────────┬───────────────────────┘
                  │
         ┌────────┴────────┐
         ▼                 ▼
    ┌─────────┐       ┌─────────┐
    │ Dex API │       │ Claude  │
    └─────────┘       │ (Claude │
                      │  Sonnet │
                      │   3.5)  │
                      └─────────┘
         │
         ▼
    ┌─────────────┐
    │ PostgreSQL  │
    └─────────────┘
```

**Key Design Principles:**
- **Internal API only** - No direct user exposure
- **Async throughout** - Uses httpx and asyncio for non-blocking I/O
- **Consumer-driven** - SDK, CLI, and MCP wrappers handle user interaction
- **Stateless** - Each request is independent, database is single source of truth
- **Rate-limited** - Built-in delays prevent API throttling (1-second between Claude calls)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or use docker-compose)
- Dex API key (from https://app.getdex.com/settings/api)
- Anthropic/Claude API key (from https://console.anthropic.com/settings/keys)

### Setup

1. **Clone and install:**
   ```bash
   cd ~/src/products/ultradex
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database URL
   ```

3. **Initialize database:**
   ```bash
   python -m alembic upgrade head  # (run migrations when available)
   ```

4. **Run locally:**
   ```bash
   uvicorn api.main:app --reload
   ```

   API will be available at `http://localhost:8000`

### Docker Setup

```bash
# Build and run with docker-compose
docker-compose up --build

# API available at http://localhost:8000
# PostgreSQL available at localhost:5432
```

## API Endpoints

### Contacts

- `GET /api/v1/contacts` - List all cached contacts
- `GET /api/v1/contacts/{id}` - Get specific contact
- `GET /api/v1/contacts/neglected/list` - Get neglected contacts (value ≥60, days ≥30)
- `POST /api/v1/contacts/sync` - Sync all contacts from Dex
- `POST /api/v1/contacts/{id}/note` - Write note to contact in Dex

### Analysis

- `POST /api/v1/analyze` - Run AI analysis on contacts
  - Optional: `?limit=10` to analyze only N contacts
- `GET /api/v1/analyze/runs` - Get recent analysis runs
- `GET /api/v1/analyze/runs/{id}` - Get specific analysis run details
- `GET /api/v1/stats` - Get aggregate analysis statistics

### Health

- `GET /health` - Basic health check
- `GET /health/db` - Database connectivity check
- `GET /health/ready` - Kubernetes readiness probe

## Contact Analysis

### Value Scoring (0-100)

Claude analyzes contacts based on:
- **Professional influence** - Seniority, reach, industry standing
- **Mutual benefit potential** - Alignment with your goals and theirs
- **Relationship strength** - Historical interaction quality from notes
- **Industry relevance** - Tech, AI, business sector fit

### Neglected Contact Detection

A contact is flagged as neglected when:
- Value score ≥ 60 (high value)
- Days since last contact ≥ 30 (stale)

### Output

Each analysis produces:
```json
{
  "value_score": 75,
  "reason": "VP of Engineering at AI startup with 2 recent conversations. Potential partnership opportunity.",
  "outreach_strategy": "Reference last conversation about LLM APIs. Send article on token optimization.",
  "suggested_timing": "Within 2 weeks"
}
```

## Cost Tracking

- **Estimate:** ~500 tokens per contact (input + output)
- **Weekly analysis of 200 contacts:** ~$0.50/run, ~$2-3/month
- **Claude Sonnet 3.5 pricing:** ~$3 per 1M tokens

All analysis runs are tracked in the database for cost analysis.

## Data Models

### Contact
```python
ContactDB:
  - id: str (Dex contact ID)
  - name, email, company, job_title, phone, notes
  - last_contacted: DateTime (tracked externally)
  - ai_value: float (0-100 score)
  - ai_reason: str (explanation)
  - outreach_strategy: str (personalized strategy)
  - last_analyzed: DateTime (7-day cache)
```

### AnalysisRun
```python
AnalysisRunDB:
  - id: UUID
  - timestamp: DateTime
  - contacts_analyzed: int
  - neglected_contacts_found: int
  - estimated_tokens: int
  - estimated_cost: float
  - success: bool
  - error_message: str (if failed)
```

## Rate Limiting

- **Dex API:** Pagination with 100 contacts per request, automatic batching
- **Claude API:** 1-second delay between calls to prevent throttling
- **Database:** Connection pooling via SQLAlchemy

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

HTTP status codes:
- `200` - Success
- `400` - Bad request (missing fields, validation)
- `404` - Not found (contact, analysis run)
- `500` - Server error (API failure, database error)
- `503` - Service unavailable (database down)

## Development

### Project Structure

```
ultradex/
├── core/                    # Business logic
│   ├── models.py            # Data models (Pydantic + SQLAlchemy)
│   ├── database.py          # Database setup & sessions
│   ├── dex_client.py        # Dex REST API integration
│   ├── claude_client.py     # Claude AI integration
│   └── contact_analyzer.py  # Analysis orchestration
├── api/                     # FastAPI server
│   ├── main.py              # App initialization & DI
│   └── routes/              # Endpoint handlers
│       ├── contacts.py
│       ├── analysis.py
│       └── health.py
├── sdk/                     # Python SDK (Phase 2)
├── mcp/                     # MCP Server (Phase 3)
├── cli/                     # Go CLI (Phase 4)
└── migrations/              # Alembic database migrations
```

### Testing

```bash
# Run tests (when added)
pytest tests/

# Type checking
mypy api core
```

### Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn api.main:app --reload --log-level debug

# Check app state in Python REPL
from api.main import app_state
print(app_state)
```

## Next Phases

- **Phase 2:** Python SDK wrapper around HTTP API
- **Phase 3:** MCP Server for Jarvis integration
- **Phase 4:** Go CLI for admin/ops operations
- **Phase 5:** Scheduled background analysis (Celery or similar)
- **Phase 6:** Advanced filtering and search
- **Phase 7:** Export and reporting

## References

- [Dex API Docs](https://api.getdex.com/)
- [Anthropic API Reference](https://docs.anthropic.com/claude/reference/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/)
