# Ultradex Python SDK

Production-ready Python SDK for the Ultradex API with async/sync support, automatic polling, and comprehensive error handling.

## Features

✅ **Async-first design** - Built on `httpx` and `asyncio` for high concurrency
✅ **Sync wrapper** - Drop-in synchronous functions for simple use cases
✅ **Automatic polling** - Handles operation status polling transparently
✅ **Idempotency** - Built-in deduplication with idempotency keys
✅ **Event tracking** - Access full audit trail of operation events
✅ **Type hints** - Full Python type annotations
✅ **Error handling** - Graceful error handling with meaningful exceptions
✅ **CLI tool** - Command-line interface for common operations

## Installation

### From Source

```bash
cd /Users/nate/src/products/ultradex
pip install -e .
```

### Dependencies

```
httpx>=0.24.0
click>=8.0.0  # For CLI tool
```

## Quick Start

### 30-Second Example

```python
from sdk.ultradex_sdk import analyze_contacts

# Synchronous - simplest approach
result = analyze_contacts(limit=50)
print(f"Analyzed: {result['result']['analyzed']}")
```

### Async Example

```python
import asyncio
from sdk.ultradex_sdk import UltradexClient

async def main():
    async with UltradexClient("http://localhost:8000") as client:
        result = await client.analyze_contacts(limit=50)
        print(f"Status: {result['status']}")

asyncio.run(main())
```

### CLI Example

```bash
# Analyze contacts
ultradex analyze --limit 50

# Check status
ultradex status op-abc123

# View events
ultradex events op-abc123

# Sync contacts
ultradex sync
```

## Documentation

- **[SDK_GUIDE.md](./SDK_GUIDE.md)** - Complete API reference and usage patterns
- **[examples/integration_examples.py](./examples/integration_examples.py)** - Real-world integration patterns
- **[REFACTORING_COMPLETE.md](./REFACTORING_COMPLETE.md)** - Architecture and design

## Core Concepts

### Operations

Every API command returns an `operation_id` for tracking:

```
POST /api/v2/contacts/commands/analyze → 202 Accepted
  Returns: {"id": "op-abc123", "status": "accepted"}

GET /api/v2/operations/op-abc123 → {"status": "running", ...}
  Eventually: {"status": "completed", "result": {...}}
```

### Polling

The SDK automatically polls until operation completes:

```python
# SDK handles polling internally
result = await client.analyze_contacts(limit=50)
# Blocks until status is "completed" or "failed"
```

### Idempotency

Use idempotency keys to prevent duplicate executions within 24 hours:

```python
# This request is deduplicated
result = await client.analyze_contacts(
    limit=50,
    idempotency_key="daily-sync-2026-02-14"
)

# Same key returns cached result
result2 = await client.analyze_contacts(
    limit=50,
    idempotency_key="daily-sync-2026-02-14"
)
# result == result2, no duplicate work
```

### Events

Track operation progress via immutable event log:

```python
events = await client.get_operation_events("op-abc123")

# Returns:
# [
#   {"event_type": "operation.accepted", "timestamp": "..."},
#   {"event_type": "task.started", "timestamp": "..."},
#   {"event_type": "task.completed", "timestamp": "..."}
# ]
```

## API Reference

### UltradexClient

```python
class UltradexClient:
    async def analyze_contacts(
        limit: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]

    async def sync_contacts(
        idempotency_key: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]

    async def get_operation(operation_id: str) -> Dict[str, Any]

    async def get_operation_events(operation_id: str) -> list

    async def close()
```

### Convenience Functions

```python
from sdk.ultradex_sdk import analyze_contacts, sync_contacts

# Synchronous wrappers
result = analyze_contacts(limit=50)
result = sync_contacts()
```

## Common Patterns

### Pattern 1: Async Context Manager (Recommended)

```python
async with UltradexClient("http://localhost:8000") as client:
    result = await client.analyze_contacts()
```

### Pattern 2: Sync Wrapper

```python
result = analyze_contacts(limit=50)
```

### Pattern 3: Fire-and-Forget

```python
# Submit and return operation_id immediately
response = await client.client.post(
    "/api/v2/contacts/commands/analyze",
    json={"limit": 50}
)
operation_id = response.json()["id"]
# Return to caller, they poll later
```

### Pattern 4: Batch Processing

```python
results = await asyncio.gather(
    client.analyze_contacts(limit=10),
    client.analyze_contacts(limit=20),
    client.analyze_contacts(limit=30),
)
```

### Pattern 5: Error Handling

```python
try:
    result = await client.analyze_contacts(limit=50)
except TimeoutError:
    print("Operation took too long")
except httpx.HTTPStatusError as e:
    print(f"API error: {e.response.status_code}")
```

## CLI Usage

### Commands

```bash
# Analyze contacts
ultradex analyze [--limit=N] [--wait=SECONDS] [--key=KEY] [--verbose]

# Sync contacts
ultradex sync [--wait=SECONDS] [--key=KEY] [--verbose]

# Check operation status
ultradex status <operation_id> [--verbose]

# View operation events
ultradex events <operation_id>

# Show configuration
ultradex config

# Check API health
ultradex health
```

### Configuration

```bash
export ULTRADEX_API_URL="http://localhost:8000"
export ULTRADEX_API_KEY="your-bearer-token"

ultradex analyze --limit 100
```

## Integration Examples

See [examples/integration_examples.py](./examples/integration_examples.py) for:

1. Scheduled daily analysis
2. Batch processing with progress tracking
3. Concurrent operations
4. Long-running tasks with status updates
5. Error handling with retry logic
6. Webhook-style fire-and-forget
7. Database-backed operation tracking
8. Rate limiting

## Testing

### Unit Test Template

```python
import pytest
from unittest.mock import patch, MagicMock
from sdk.ultradex_sdk import UltradexClient

@pytest.mark.asyncio
async def test_analyze_contacts():
    with patch('sdk.ultradex_sdk.httpx.AsyncClient') as mock:
        # Setup mock
        mock.return_value.post.return_value.json.return_value = {"id": "op-123"}
        mock.return_value.get.return_value.json.side_effect = [
            {"status": "pending"},
            {"status": "completed", "result": {"analyzed": 50}}
        ]

        # Test
        client = UltradexClient("http://localhost:8000")
        result = await client.analyze_contacts(limit=50)

        assert result["status"] == "completed"
        assert result["result"]["analyzed"] == 50
```

## Performance

### Connection Pooling

httpx automatically manages connection pools:

```python
# Default: 100 connections per host
async with UltradexClient("http://localhost:8000") as client:
    # Connection reused across requests
    result1 = await client.analyze_contacts()
    result2 = await client.analyze_contacts()
```

### Polling Interval

Customize polling for your use case:

```python
# Slower polling for long tasks (reduces API load)
result = await client._poll_operation(
    operation_id,
    timeout=3600,
    poll_interval=10  # Check every 10 seconds
)
```

## Troubleshooting

### "Connection refused"
- Ensure API is running: `docker-compose up api`
- Check `ULTRADEX_API_URL` is correct

### "Operation did not complete in timeout"
- Increase `poll_timeout`: `poll_timeout=3600`
- Check API logs for errors

### "Idempotency-Key already used"
- Wait 24 hours or use unique key each time

## Architecture

The SDK implements the **intent-first async pattern**:

```
1. Submit command → 202 Accepted + operation_id
2. Client polls: GET /api/v2/operations/{operation_id}
3. Status transitions: pending → running → completed
4. Optional: GET /api/v1/operations/{operation_id}/events (audit trail)
```

See [REFACTORING_COMPLETE.md](./REFACTORING_COMPLETE.md) for full architecture.

## Contributing

To extend the SDK:

1. Add methods to `UltradexClient` class
2. Update type hints
3. Add docstrings
4. Add integration examples
5. Update this README

## License

Same as Ultradex project.

## Support

- **Docs**: [SDK_GUIDE.md](./SDK_GUIDE.md)
- **Examples**: [examples/](./examples/)
- **API Reference**: [REFACTORING_COMPLETE.md](./REFACTORING_COMPLETE.md)
