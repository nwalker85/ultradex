# Ultradex Python SDK Guide

Complete guide to integrating Ultradex into your Python applications.

## Installation

```bash
pip install ultradex-sdk
# or from source
pip install -e .
```

## Quick Start

### Async Usage (Recommended)

```python
import asyncio
from sdk.ultradex_sdk import UltradexClient

async def main():
    async with UltradexClient("http://localhost:8000") as client:
        # Analyze contacts and wait for completion
        result = await client.analyze_contacts(limit=50)
        print(f"Analyzed: {result['result']['analyzed']}")
        print(f"Status: {result['status']}")

asyncio.run(main())
```

### Sync Usage (Simple Integration)

```python
from sdk.ultradex_sdk import analyze_contacts

# Just call the function - handles polling internally
result = analyze_contacts(limit=50)
print(f"Done! Result: {result}")
```

## API Reference

### UltradexClient

Main client for interacting with Ultradex API.

#### Constructor

```python
client = UltradexClient(
    api_url="http://localhost:8000",  # Ultradex API URL
    api_key=None,                       # Optional Bearer token
    timeout=30                          # HTTP timeout in seconds
)
```

#### Methods

##### `analyze_contacts(limit, idempotency_key, poll_timeout)`

Analyze contacts asynchronously with automatic polling.

```python
result = await client.analyze_contacts(
    limit=50,                           # Max contacts to analyze
    idempotency_key="my-unique-key",    # Optional: prevents duplicate runs
    poll_timeout=600                    # Max seconds to wait (default 10 min)
)

# Result structure
{
    "id": "op-abc123",
    "status": "completed",
    "created_at": "2026-02-14T10:30:00Z",
    "started_at": "2026-02-14T10:30:01Z",
    "completed_at": "2026-02-14T10:35:00Z",
    "result": {
        "analyzed": 50,
        "neglected": 12,
        "tokens": 5000,
        "cost": 0.05
    }
}
```

##### `sync_contacts(idempotency_key, poll_timeout)`

Sync all contacts from Dex to local database.

```python
result = await client.sync_contacts(
    idempotency_key="my-sync-key",
    poll_timeout=300
)
```

##### `get_operation(operation_id)`

Check status of a running operation without polling.

```python
op = await client.get_operation("op-abc123")
print(op["status"])  # "pending", "running", "completed", or "failed"
```

##### `get_operation_events(operation_id)`

Get chronological event log for an operation.

```python
events = await client.get_operation_events("op-abc123")
for event in events:
    print(f"{event['event_type']}: {event['timestamp']}")

# Output:
# operation.accepted: 2026-02-14T10:30:00Z
# task.started: 2026-02-14T10:30:01Z
# task.completed: 2026-02-14T10:35:00Z
```

#### Context Manager

Always use async context manager to ensure resources are cleaned up:

```python
async with UltradexClient("http://localhost:8000") as client:
    result = await client.analyze_contacts()
```

Or manually close:

```python
client = UltradexClient("http://localhost:8000")
try:
    result = await client.analyze_contacts()
finally:
    await client.close()
```

## Usage Patterns

### Pattern 1: Fire-and-Forget with Manual Polling

Submit work and check status later:

```python
async with UltradexClient("http://localhost:8000") as client:
    # Submit command
    response = await client.client.post(
        "/api/v2/contacts/commands/analyze",
        json={"limit": 50}
    )
    operation_id = response.json()["id"]

    # Do other work
    print(f"Operation {operation_id} submitted")

    # Check status later
    op = await client.get_operation(operation_id)
    if op["status"] == "completed":
        print(f"Results: {op['result']}")
```

### Pattern 2: Async with Long Timeout

For heavy workloads, increase timeout:

```python
result = await client.analyze_contacts(
    limit=1000,
    poll_timeout=3600  # Wait up to 1 hour
)
```

### Pattern 3: Idempotent Requests

Use idempotency keys to prevent duplicate executions:

```python
# This request is deduplicated for 24 hours
result = await client.analyze_contacts(
    limit=50,
    idempotency_key="daily-sync-2026-02-14"
)

# Same key within 24 hours returns cached result
result2 = await client.analyze_contacts(
    limit=50,
    idempotency_key="daily-sync-2026-02-14"
)
# result == result2, no duplicate work
```

### Pattern 4: Batch Processing with Concurrency

Process multiple operations in parallel:

```python
import asyncio

async def batch_analyze(client, limits):
    """Analyze multiple contact groups concurrently"""
    tasks = [
        client.analyze_contacts(limit=limit)
        for limit in limits
    ]
    return await asyncio.gather(*tasks)

# Analyze 5 groups of different sizes
async with UltradexClient("http://localhost:8000") as client:
    results = await batch_analyze(client, [10, 20, 30, 40, 50])
    total_analyzed = sum(r["result"]["analyzed"] for r in results)
    print(f"Total analyzed: {total_analyzed}")
```

### Pattern 5: Error Handling with Retry

Graceful error handling with exponential backoff:

```python
import asyncio

async def analyze_with_retry(client, limit, max_retries=3):
    """Analyze with automatic retry on timeout"""
    for attempt in range(max_retries):
        try:
            return await client.analyze_contacts(
                limit=limit,
                poll_timeout=600
            )
        except TimeoutError as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            print(f"Timeout, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"Error: {e}")
            raise

# Use it
async with UltradexClient("http://localhost:8000") as client:
    result = await analyze_with_retry(client, limit=100)
```

### Pattern 6: Progress Tracking

Check events to understand work progress:

```python
async def analyze_with_progress(client, limit):
    """Analyze and track progress via events"""
    # Submit command
    response = await client.client.post(
        "/api/v2/contacts/commands/analyze",
        json={"limit": limit}
    )
    operation_id = response.json()["id"]

    # Poll and show events
    while True:
        op = await client.get_operation(operation_id)

        if op["status"] == "running":
            events = await client.get_operation_events(operation_id)
            print(f"Events: {len(events)}")

        if op["status"] in ["completed", "failed"]:
            return op

        await asyncio.sleep(2)

# Use it
async with UltradexClient("http://localhost:8000") as client:
    result = await analyze_with_progress(client, limit=100)
```

## Authentication

### No Authentication (Local/Development)

```python
client = UltradexClient("http://localhost:8000")
```

### Bearer Token Authentication

```python
client = UltradexClient(
    "http://api.ultradex.example.com",
    api_key="your-bearer-token"
)
```

### Environment Variable

```python
import os

api_key = os.getenv("ULTRADEX_API_KEY")
client = UltradexClient(
    os.getenv("ULTRADEX_API_URL", "http://localhost:8000"),
    api_key=api_key
)
```

## Error Handling

### Common Exceptions

```python
import httpx

async with UltradexClient("http://localhost:8000") as client:
    try:
        result = await client.analyze_contacts(limit=50)
    except httpx.HTTPStatusError as e:
        # API returned error (4xx/5xx)
        print(f"API Error: {e.response.status_code}")
    except httpx.TimeoutException:
        # Request timed out
        print("Request timed out")
    except TimeoutError:
        # Operation polling timed out
        print("Operation did not complete in time")
    except Exception as e:
        # Other errors
        print(f"Error: {e}")
```

## Examples

### Example 1: Simple Sync Analysis

```python
#!/usr/bin/env python3
"""Simple synchronous contact analysis"""

from sdk.ultradex_sdk import analyze_contacts

result = analyze_contacts(limit=50)
print(f"Status: {result['status']}")
print(f"Analyzed: {result['result']['analyzed']}")
```

### Example 2: Async with Event Tracking

```python
#!/usr/bin/env python3
"""Async analysis with event tracking"""

import asyncio
from sdk.ultradex_sdk import UltradexClient

async def main():
    async with UltradexClient("http://localhost:8000") as client:
        # Analyze
        result = await client.analyze_contacts(limit=100)

        # Get events
        events = await client.get_operation_events(result["id"])

        print(f"Operation: {result['id']}")
        print(f"Status: {result['status']}")
        print(f"Events:")
        for event in events:
            print(f"  - {event['event_type']} @ {event['timestamp']}")

asyncio.run(main())
```

### Example 3: Batch Sync

```python
#!/usr/bin/env python3
"""Batch sync with concurrent requests"""

import asyncio
from sdk.ultradex_sdk import UltradexClient

async def main():
    async with UltradexClient("http://localhost:8000") as client:
        # Sync 3 times concurrently
        results = await asyncio.gather(
            client.sync_contacts(idempotency_key="sync-1"),
            client.sync_contacts(idempotency_key="sync-2"),
            client.sync_contacts(idempotency_key="sync-3"),
        )

        for i, result in enumerate(results):
            print(f"Sync {i+1}: {result['status']}")

asyncio.run(main())
```

## Testing

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sdk.ultradex_sdk import UltradexClient

@pytest.mark.asyncio
async def test_analyze_contacts():
    # Mock the HTTP client
    with patch('sdk.ultradex_sdk.httpx.AsyncClient') as mock_client:
        # Setup mock responses
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {"id": "op-123"},  # Initial submit
            {"status": "pending"},  # First poll
            {"status": "completed", "result": {"analyzed": 50}}  # Final
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.post.return_value = mock_response
        mock_client.return_value.get.return_value = mock_response

        # Test
        client = UltradexClient("http://localhost:8000")
        result = await client.analyze_contacts(limit=50)

        assert result["status"] == "completed"
        assert result["result"]["analyzed"] == 50
```

## Performance Considerations

### Polling Interval

Default polling interval is 1 second. Adjust for your use case:

```python
# Slower polling for long-running tasks (reduces API load)
result = await client._poll_operation(
    operation_id,
    timeout=3600,
    poll_interval=10  # Check every 10 seconds
)

# Faster polling for real-time feedback
result = await client._poll_operation(
    operation_id,
    timeout=60,
    poll_interval=0.5  # Check every 500ms
)
```

### Connection Pooling

httpx automatically manages connection pooling. For high-concurrency scenarios:

```python
import httpx
from sdk.ultradex_sdk import UltradexClient

# Create client with connection pool limits
async with UltradexClient(
    "http://localhost:8000",
    timeout=60
) as client:
    # httpx manages connection pooling internally
    # Default limits: 100 connections per host
    result = await client.analyze_contacts()
```

## Troubleshooting

### "Connection refused"

```python
# Check API is running
# Error: Cannot connect to http://localhost:8000

# Solution: Start API server
# docker-compose up api
```

### "Operation did not complete in timeout"

```python
# Increase timeout
result = await client.analyze_contacts(
    limit=50,
    poll_timeout=3600  # 1 hour instead of 10 minutes
)
```

### "Idempotency-Key already used"

```python
# Idempotency key conflicts within 24-hour window
# Use unique keys or wait 24 hours

import uuid
result = await client.analyze_contacts(
    idempotency_key=str(uuid.uuid4())
)
```

## Next Steps

- See `/api/v2/contacts/commands/analyze` for API details
- See `core/models.py` for operation/event schemas
- See `REFACTORING_COMPLETE.md` for architecture overview
