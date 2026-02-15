"""Ultradex Python SDK for async operation submission and polling"""

import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime


class UltradexClient:
    """Client for Ultradex API with built-in polling and retry logic"""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize Ultradex client.

        Args:
            api_url: Base URL of Ultradex API
            api_key: Optional API key for authentication
            timeout: HTTP timeout in seconds
        """
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=api_url,
            timeout=timeout,
            headers=self._get_headers()
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def analyze_contacts(
        self,
        limit: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]:
        """
        Analyze contacts asynchronously.

        Args:
            limit: Max contacts to analyze
            idempotency_key: Optional key for deduplication
            poll_timeout: Max seconds to wait for completion

        Returns:
            Operation result with analysis data
        """
        # Submit command
        headers = self._get_headers().copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        response = await self.client.post(
            "/api/v2/contacts/commands/analyze",
            json={"limit": limit} if limit else {},
            headers=headers
        )
        response.raise_for_status()
        operation = response.json()
        operation_id = operation["id"]

        # Poll for completion
        return await self._poll_operation(operation_id, poll_timeout)

    async def sync_contacts(
        self,
        idempotency_key: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]:
        """
        Sync contacts asynchronously.

        Args:
            idempotency_key: Optional key for deduplication
            poll_timeout: Max seconds to wait for completion

        Returns:
            Operation result with sync data
        """
        # Submit command
        headers = self._get_headers().copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        response = await self.client.post(
            "/api/v2/contacts/commands/sync",
            headers=headers
        )
        response.raise_for_status()
        operation = response.json()
        operation_id = operation["id"]

        # Poll for completion
        return await self._poll_operation(operation_id, poll_timeout)

    async def get_operation(self, operation_id: str) -> Dict[str, Any]:
        """Get operation status"""
        response = await self.client.get(
            f"/api/v2/operations/{operation_id}"
        )
        response.raise_for_status()
        return response.json()

    async def get_operation_events(self, operation_id: str) -> list:
        """Get events for an operation"""
        response = await self.client.get(
            f"/api/v1/operations/{operation_id}/events"
        )
        response.raise_for_status()
        return response.json()

    async def _poll_operation(
        self,
        operation_id: str,
        timeout: int = 600,
        poll_interval: int = 1
    ) -> Dict[str, Any]:
        """
        Poll for operation completion.

        Args:
            operation_id: Operation to poll
            timeout: Max seconds to wait
            poll_interval: Seconds between polls

        Returns:
            Completed operation
        """
        start_time = datetime.now()

        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                raise TimeoutError(f"Operation {operation_id} did not complete in {timeout}s")

            operation = await self.get_operation(operation_id)
            status = operation.get("status")

            if status in ["completed", "failed"]:
                return operation

            await asyncio.sleep(poll_interval)

    async def close(self):
        """Close the client"""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Convenience functions for sync usage
def analyze_contacts(
    limit: Optional[int] = None,
    api_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """Synchronous wrapper for analyze"""
    async def _run():
        async with UltradexClient(api_url) as client:
            return await client.analyze_contacts(limit=limit)

    return asyncio.run(_run())


def sync_contacts(api_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Synchronous wrapper for sync"""
    async def _run():
        async with UltradexClient(api_url) as client:
            return await client.sync_contacts()

    return asyncio.run(_run())
