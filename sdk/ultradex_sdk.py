"""Ultradex Python SDK for async operation submission and polling"""

import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
from ravenhelm_contracts import ContractHandleV1


class UltradexClient:
    """Client for Ultradex API with built-in polling and retry logic"""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
        transport: Optional[httpx.AsyncBaseTransport] = None,
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
            headers=self._get_headers(),
            transport=transport,
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def submit_analyze_contacts(
        self,
        limit: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        """Submit an analyze command and return its governed handle."""
        headers = self._get_headers().copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if actor_id:
            headers["X-Actor-Id"] = actor_id
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        response = await self.client.post(
            "/api/v2/contacts/commands/analyze",
            json={"limit": limit} if limit else {},
            headers=headers
        )
        response.raise_for_status()
        return ContractHandleV1.from_dict(response.json())

    async def submit_sync_contacts(
        self,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        """Submit a sync command and return its governed handle."""
        headers = self._get_headers().copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if actor_id:
            headers["X-Actor-Id"] = actor_id
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        response = await self.client.post(
            "/api/v2/contacts/commands/sync",
            json={},
            headers=headers
        )
        response.raise_for_status()
        return ContractHandleV1.from_dict(response.json())

    async def analyze_contacts(
        self,
        limit: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]:
        """Submit an analyze command and wait for its terminal projection."""
        handle = await self.submit_analyze_contacts(
            limit=limit,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        return await self._poll_operation(handle.operation_id, poll_timeout)

    async def sync_contacts(
        self,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]:
        """Submit a sync command and wait for its terminal projection."""
        handle = await self.submit_sync_contacts(
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        return await self._poll_operation(handle.operation_id, poll_timeout)

    async def _graphql(
        self,
        query: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        response = await self.client.post(
            "/api/graphql",
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL projection failed: {payload['errors']}")
        return payload["data"]

    async def get_operation(self, operation_id: str) -> Dict[str, Any]:
        """Read an operation from the GraphQL projection surface."""
        data = await self._graphql(
            """
            query Operation($operationId: String!) {
              operation(id: $operationId) {
                id
                correlation_id: correlationId
                command
                status
                created_at: createdAt
                started_at: startedAt
                completed_at: completedAt
                result
                error
              }
            }
            """,
            {"operationId": operation_id},
        )
        return data["operation"]

    async def get_operation_events(self, operation_id: str) -> list:
        """Read an operation lifecycle from the GraphQL projection surface."""
        data = await self._graphql(
            """
            query Events($operationId: String!) {
              events(operationId: $operationId) {
                id
                operation_id: operationId
                event_type: eventType
                timestamp
                payload
              }
            }
            """,
            {"operationId": operation_id},
        )
        return data["events"]

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

            if status in {
                "completed",
                "failed",
                "succeeded",
                "cancelled",
                "expired",
                "revoked",
                "refused",
                "unverifiable",
            }:
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
