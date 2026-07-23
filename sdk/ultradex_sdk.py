"""Ultradex Python SDK for async operation submission and polling"""

import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
from ravenhelm_contracts import (
    ContractHandleV1,
    CorrelationContextV1,
    JobSearchCommandV1,
)


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

    @staticmethod
    def _contract_handle_response(response: httpx.Response) -> ContractHandleV1:
        """Return governed success/failure handles before generic HTTP errors."""
        if response.status_code in {202, 503}:
            return ContractHandleV1.from_dict(response.json())
        response.raise_for_status()
        return ContractHandleV1.from_dict(response.json())

    async def submit_analyze_contacts(
        self,
        limit: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        """Submit an analyze command and return its governed handle."""
        headers = self._get_headers().copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        # Kept as a source-compatible argument for 1.x callers. The server
        # derives actor identity from the bearer credential and ignores spoofable
        # caller identity headers.
        if delegation_id:
            headers["X-Delegation-Id"] = delegation_id
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        response = await self.client.post(
            "/api/v2/contacts/commands/analyze",
            json={"limit": limit} if limit is not None else {},
            headers=headers
        )
        return self._contract_handle_response(response)

    async def submit_sync_contacts(
        self,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        """Submit a sync command and return its governed handle."""
        headers = self._get_headers().copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        # ``actor_id`` remains source-compatible but is intentionally not sent.
        if delegation_id:
            headers["X-Delegation-Id"] = delegation_id
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        response = await self.client.post(
            "/api/v2/contacts/commands/sync",
            json={},
            headers=headers
        )
        return self._contract_handle_response(response)

    @staticmethod
    def _validate_jobsearch_parameters(
        command: str,
        parameters: Dict[str, object],
        idempotency_key: str,
    ) -> None:
        """Validate with the shared contract without sending server-owned context."""
        token = str(uuid.uuid4())
        actor_id = "sdk-client"
        context = CorrelationContextV1.from_dict(
            {
                "tenant_id": "private",
                "operation_id": f"sdk-operation-{token}",
                "contract_id": f"sdk-operation-{token}",
                "correlation_id": f"sdk-correlation-{token}",
                "causation_id": f"sdk-request-{token}",
                "execution_id": f"sdk-execution-{token}",
                "actor_id": actor_id,
                "request_id": f"sdk-request-{token}",
                "trace_id": f"sdk-trace-{token}",
                "service_name": "ultradex-python-sdk",
                "service_version": "1.1.0",
                "deployment_sha": "sdk-client",
                "environment": "local",
                "contract_version": "jobsearch.v1",
                "schema_version": "control-surface.v1",
            }
        )
        JobSearchCommandV1.from_dict(
            {
                "command_id": f"sdk-command-{token}",
                "command": command,
                "actor_id": actor_id,
                "idempotency_key": idempotency_key,
                "context": context.to_dict(),
                "parameters": parameters,
            }
        )

    async def submit_jobsearch_command(
        self,
        command: str,
        parameters: Dict[str, object],
        *,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        """Submit one canonical job-search mutation through the official SDK."""
        self._validate_jobsearch_parameters(
            command,
            parameters,
            idempotency_key,
        )
        headers = self._get_headers().copy()
        headers["Idempotency-Key"] = idempotency_key
        if delegation_id:
            headers["X-Delegation-Id"] = delegation_id
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        response = await self.client.post(
            f"/api/v2/job-search/commands/{command}",
            json=parameters,
            headers=headers,
        )
        return self._contract_handle_response(response)

    async def submit_sources_ingest(
        self,
        *,
        source_kind: str,
        source_ref: str,
        observed_at: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "sources.ingest",
            {
                "source_kind": source_kind,
                "source_ref": source_ref,
                "observed_at": observed_at,
            },
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_opportunity_create(
        self,
        *,
        employer: str,
        title: str,
        source_evidence_id: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "opportunities.create",
            {
                "employer": employer,
                "title": title,
                "source_evidence_id": source_evidence_id,
            },
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_opportunity_score(
        self,
        *,
        opportunity_id: str,
        lens: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "opportunities.score",
            {"opportunity_id": opportunity_id, "lens": lens},
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_application_transition(
        self,
        *,
        application_id: str,
        status: str,
        occurred_at: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "applications.transition",
            {
                "application_id": application_id,
                "status": status,
                "occurred_at": occurred_at,
            },
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_relationship_sync(
        self,
        *,
        opportunity_id: str,
        dex_contact_ref: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "relationships.sync",
            {
                "opportunity_id": opportunity_id,
                "dex_contact_ref": dex_contact_ref,
            },
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_outreach_prepare(
        self,
        *,
        opportunity_id: str,
        channel: str,
        message_commitment: str,
        idempotency_key: str,
        relationship_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        parameters: Dict[str, object] = {
            "opportunity_id": opportunity_id,
            "channel": channel,
            "message_commitment": message_commitment,
        }
        if relationship_id is not None:
            parameters["relationship_id"] = relationship_id
        return await self.submit_jobsearch_command(
            "outreach.prepare",
            parameters,
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_outreach_approve(
        self,
        *,
        outreach_id: str,
        message_commitment: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "outreach.approve",
            {
                "outreach_id": outreach_id,
                "message_commitment": message_commitment,
            },
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_outreach_send(
        self,
        *,
        outreach_id: str,
        approval_contract_id: str,
        message_commitment: str,
        channel: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "outreach.send",
            {
                "outreach_id": outreach_id,
                "approval_contract_id": approval_contract_id,
                "message_commitment": message_commitment,
                "channel": channel,
            },
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def submit_evidence_export(
        self,
        *,
        subject_type: str,
        subject_id: str,
        profile: str,
        idempotency_key: str,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContractHandleV1:
        return await self.submit_jobsearch_command(
            "evidence.export",
            {
                "subject_type": subject_type,
                "subject_id": subject_id,
                "profile": profile,
            },
            idempotency_key=idempotency_key,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )

    async def analyze_contacts(
        self,
        limit: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]:
        """Submit an analyze command and wait for its terminal projection."""
        handle = await self.submit_analyze_contacts(
            limit=limit,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )
        return await self._poll_operation(handle.operation_id, poll_timeout)

    async def sync_contacts(
        self,
        idempotency_key: Optional[str] = None,
        actor_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        poll_timeout: int = 600
    ) -> Dict[str, Any]:
        """Submit a sync command and wait for its terminal projection."""
        handle = await self.submit_sync_contacts(
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            delegation_id=delegation_id,
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

    async def get_operation_events(
        self,
        operation_id: str,
        first: int = 50,
        after: Optional[int] = None,
    ) -> list:
        """Read one bounded lifecycle page from the GraphQL projection surface."""
        data = await self._graphql(
            """
            query Events($operationId: String!, $first: Int!, $after: Int) {
              events(operationId: $operationId, first: $first, after: $after) {
                id
                operation_id: operationId
                event_type: eventType
                timestamp
                payload
              }
            }
            """,
            {"operationId": operation_id, "first": first, "after": after},
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
