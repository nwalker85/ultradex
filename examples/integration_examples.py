"""
Ultradex SDK Integration Examples

Real-world patterns for integrating Ultradex into applications.
"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sdk.ultradex_sdk import UltradexClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Scheduled Daily Analysis
# ============================================================================

async def example_scheduled_analysis():
    """
    Run contact analysis on a schedule (e.g., daily).

    Use case: Nightly analysis job that runs at 2 AM.
    """
    logger.info("Example 1: Scheduled Daily Analysis")

    api_url = "http://localhost:8000"

    async with UltradexClient(api_url) as client:
        # Use date-based idempotency key to prevent duplicate runs
        today = datetime.now().strftime("%Y-%m-%d")
        idempotency_key = f"daily-analysis-{today}"

        logger.info(f"Submitting analysis with key: {idempotency_key}")

        # This will run once per day even if called multiple times
        result = await client.analyze_contacts(
            limit=1000,
            idempotency_key=idempotency_key,
            poll_timeout=3600  # Allow up to 1 hour
        )

        logger.info(f"Analysis complete: {result['result']}")
        return result


# ============================================================================
# Example 2: Batch Processing with Progress Tracking
# ============================================================================

async def example_batch_processing():
    """
    Process multiple batches sequentially with progress tracking.

    Use case: Analyzing contacts in batches of 100 each.
    """
    logger.info("Example 2: Batch Processing with Progress Tracking")

    api_url = "http://localhost:8000"
    batch_size = 100
    total_contacts = 500
    num_batches = (total_contacts + batch_size - 1) // batch_size

    results = []

    async with UltradexClient(api_url) as client:
        for i in range(num_batches):
            batch_num = i + 1
            logger.info(f"Processing batch {batch_num}/{num_batches}")

            try:
                result = await client.analyze_contacts(
                    limit=batch_size,
                    poll_timeout=600
                )

                analyzed = result["result"]["analyzed"]
                logger.info(f"✅ Batch {batch_num}: Analyzed {analyzed} contacts")

                results.append(result)

            except TimeoutError:
                logger.error(f"❌ Batch {batch_num}: Timed out")
                raise

            except Exception as e:
                logger.error(f"❌ Batch {batch_num}: {e}")
                raise

    total_analyzed = sum(r["result"]["analyzed"] for r in results)
    logger.info(f"✅ Total analyzed: {total_analyzed}")

    return results


# ============================================================================
# Example 3: Concurrent Operations
# ============================================================================

async def example_concurrent_operations():
    """
    Run multiple operations in parallel.

    Use case: Parallel syncs from different data sources.
    """
    logger.info("Example 3: Concurrent Operations")

    api_url = "http://localhost:8000"

    async with UltradexClient(api_url) as client:
        # Run 3 syncs in parallel
        logger.info("Starting 3 concurrent syncs...")

        results = await asyncio.gather(
            client.sync_contacts(idempotency_key="sync-1"),
            client.sync_contacts(idempotency_key="sync-2"),
            client.sync_contacts(idempotency_key="sync-3"),
            return_exceptions=True
        )

        # Check results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Sync {i+1} failed: {result}")
            else:
                logger.info(f"Sync {i+1} complete: {result['status']}")

    return results


# ============================================================================
# Example 4: Long-Running Task with Status Updates
# ============================================================================

async def example_long_running_with_updates():
    """
    Track a long-running operation and report progress.

    Use case: Web dashboard showing analysis progress in real-time.
    """
    logger.info("Example 4: Long-Running Task with Status Updates")

    api_url = "http://localhost:8000"

    async with UltradexClient(api_url) as client:
        # Submit without polling
        response = await client.client.post(
            f"{api_url}/api/v2/contacts/commands/analyze",
            json={"limit": 1000}
        )
        response.raise_for_status()
        operation_id = response.json()["id"]

        logger.info(f"Operation submitted: {operation_id}")

        # Poll with custom interval
        start_time = datetime.now()
        check_interval = 2  # Check every 2 seconds

        while True:
            elapsed = (datetime.now() - start_time).total_seconds()

            op = await client.get_operation(operation_id)
            status = op["status"]

            logger.info(f"[{elapsed:.0f}s] Status: {status}")

            # Optionally check events for more detailed progress
            events = await client.get_operation_events(operation_id)
            logger.info(f"  Events: {len(events)}")

            if status in ["completed", "failed"]:
                logger.info(f"✅ Final status: {status}")
                return op

            await asyncio.sleep(check_interval)


# ============================================================================
# Example 5: Error Handling with Retry Logic
# ============================================================================

async def example_error_handling_retry():
    """
    Robust error handling with exponential backoff retry.

    Use case: Production-grade API calls with resilience.
    """
    logger.info("Example 5: Error Handling with Retry Logic")

    api_url = "http://localhost:8000"
    max_retries = 3
    base_wait_time = 1  # Start with 1 second

    async with UltradexClient(api_url) as client:
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_retries}")

                result = await client.analyze_contacts(
                    limit=100,
                    poll_timeout=300
                )

                logger.info("✅ Success")
                return result

            except TimeoutError as e:
                logger.warning(f"Timeout: {e}")

                if attempt < max_retries - 1:
                    wait_time = base_wait_time * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries exceeded")
                    raise

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise

    raise Exception("All retries failed")


# ============================================================================
# Example 6: Webhook-Style Integration
# ============================================================================

async def example_webhook_style():
    """
    Submit operation and return immediately (webhook pattern).

    Use case: REST API that returns operation_id immediately.
    """
    logger.info("Example 6: Webhook-Style Integration")

    api_url = "http://localhost:8000"

    async with UltradexClient(api_url) as client:
        # Submit command without polling
        response = await client.client.post(
            f"{api_url}/api/v2/contacts/commands/analyze",
            json={"limit": 100}
        )
        response.raise_for_status()

        operation = response.json()
        operation_id = operation["id"]

        logger.info(f"Operation submitted: {operation_id}")

        # Return immediately
        return {
            "status": "accepted",
            "operation_id": operation_id,
            "status_url": f"/api/v2/operations/{operation_id}",
            "events_url": f"/api/v1/operations/{operation_id}/events"
        }


# ============================================================================
# Example 7: Database-Backed Status Tracking
# ============================================================================

class OperationTracker:
    """
    Example class for tracking operations in a database.

    Use case: Production system where you need to track operations across restarts.
    """

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.operations = {}  # In-memory; use real DB in production

    async def submit_and_track(self, command: str, **params) -> str:
        """Submit operation and track it"""
        async with UltradexClient(self.api_url) as client:
            # For this example, assume analyze command
            result = await client.analyze_contacts(
                limit=params.get("limit"),
                poll_timeout=params.get("poll_timeout", 600)
            )

            operation_id = result["id"]

            # Store in database
            self.operations[operation_id] = {
                "command": command,
                "status": result["status"],
                "result": result.get("result"),
                "submitted_at": datetime.now(),
            }

            logger.info(f"Tracked operation: {operation_id}")
            return operation_id

    def get_status(self, operation_id: str) -> Dict[str, Any]:
        """Get cached operation status"""
        return self.operations.get(operation_id, {})

    async def sync_status(self, operation_id: str) -> Dict[str, Any]:
        """Sync status from API"""
        async with UltradexClient(self.api_url) as client:
            op = await client.get_operation(operation_id)

            # Update cache
            if operation_id in self.operations:
                self.operations[operation_id].update({
                    "status": op["status"],
                    "result": op.get("result"),
                    "error": op.get("error"),
                })

            return op


async def example_db_backed_tracking():
    """Example of database-backed operation tracking"""
    logger.info("Example 7: Database-Backed Status Tracking")

    tracker = OperationTracker("http://localhost:8000")

    # Submit
    operation_id = await tracker.submit_and_track("analyze", limit=50)

    # Check cached status
    cached = tracker.get_status(operation_id)
    logger.info(f"Cached: {cached['status']}")

    # Sync from API
    synced = await tracker.sync_status(operation_id)
    logger.info(f"Synced: {synced['status']}")

    return operation_id


# ============================================================================
# Example 8: Rate Limiting
# ============================================================================

class RateLimitedClient:
    """
    Ultradex client with rate limiting.

    Use case: Ensure we don't overwhelm the API.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        requests_per_minute: int = 10
    ):
        self.api_url = api_url
        self.requests_per_minute = requests_per_minute
        self.request_times: List[datetime] = []

    async def _check_rate_limit(self):
        """Check if we can make a request"""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Remove old request times
        self.request_times = [t for t in self.request_times if t > cutoff]

        if len(self.request_times) >= self.requests_per_minute:
            # Need to wait
            oldest = self.request_times[0]
            wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()

            logger.warning(f"Rate limit: waiting {wait_time:.1f}s")
            await asyncio.sleep(max(wait_time, 0.1))

        self.request_times.append(datetime.now())

    async def analyze(self, limit: int = None) -> Dict[str, Any]:
        """Rate-limited analyze"""
        await self._check_rate_limit()

        async with UltradexClient(self.api_url) as client:
            return await client.analyze_contacts(limit=limit)


async def example_rate_limiting():
    """Example of rate limiting"""
    logger.info("Example 8: Rate Limiting")

    client = RateLimitedClient("http://localhost:8000", requests_per_minute=2)

    # Make 3 requests (should throttle the 3rd)
    for i in range(3):
        logger.info(f"Request {i + 1}")
        result = await client.analyze(limit=10)
        logger.info(f"  Status: {result['status']}")

    return True


# ============================================================================
# Main Runner
# ============================================================================

async def run_all_examples():
    """Run all examples"""
    examples = [
        ("Scheduled Analysis", example_scheduled_analysis),
        ("Batch Processing", example_batch_processing),
        ("Concurrent Operations", example_concurrent_operations),
        ("Long-Running with Updates", example_long_running_with_updates),
        ("Error Handling/Retry", example_error_handling_retry),
        ("Webhook Style", example_webhook_style),
        ("DB-Backed Tracking", example_db_backed_tracking),
        ("Rate Limiting", example_rate_limiting),
    ]

    for name, example_fn in examples:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running: {name}")
            logger.info(f"{'='*60}\n")

            await example_fn()

            logger.info(f"✅ {name} completed\n")

        except Exception as e:
            logger.error(f"❌ {name} failed: {e}\n")


if __name__ == "__main__":
    asyncio.run(run_all_examples())
