# Ultradex Python SDK

The official Python SDK is the supported client boundary for Ultradex. Commands use
REST and return the shared Ravenhelm `ContractHandleV1`; projections and lifecycle
reads use GraphQL. Consumers should not write the Ultradex database directly.

## Installation

The SDK requires Python 3.11 or newer and the Ravenhelm contracts package:

```bash
pip install ultradex-sdk ravenhelm-contracts==0.2.0
```

Internal package-index configuration is environment-owned and must not embed tokens
in this repository.

## Submit without waiting

```python
from ultradex_sdk import ContractHandleV1, UltradexClient

async with UltradexClient(
    api_url="http://localhost:8000",
    api_key="...",
) as client:
    handle: ContractHandleV1 = await client.submit_analyze_contacts(
        limit=50,
        idempotency_key="analysis-2026-07-22",
    )

    print(handle.contract_id)
    print(handle.operation_id)
    print(handle.status_url)
```

Available non-blocking methods:

```python
await client.submit_analyze_contacts(limit=None, idempotency_key=None)
await client.submit_sync_contacts(idempotency_key=None)
```

Malformed server handles fail shared contract validation instead of degrading into
untyped dictionaries.

## Read projections

```python
operation = await client.get_operation(handle.operation_id)
events = await client.get_operation_events(handle.operation_id)
```

These methods query `POST /api/graphql`. Response keys retain the legacy snake-case
projection shape for compatibility.

## Submit and wait

The original high-level methods remain available:

```python
result = await client.analyze_contacts(
    limit=50,
    idempotency_key="analysis-2026-07-22",
    poll_timeout=600,
)

result = await client.sync_contacts(
    idempotency_key="sync-2026-07-22",
    poll_timeout=600,
)
```

They call the typed `submit_*` method and then poll the GraphQL projection using
`handle.operation_id` until `completed` or `failed`.

## Synchronous wrappers

```python
from ultradex_sdk import analyze_contacts, sync_contacts

analysis = analyze_contacts(limit=25)
sync = sync_contacts()
```

Do not use these wrappers from an already-running event loop.

## Errors

- HTTP failures raise `httpx.HTTPStatusError`.
- Invalid contract handles raise `ValueError` from the shared contract package.
- GraphQL response errors raise `RuntimeError`.
- Poll timeouts raise `TimeoutError`.

## Build verification

```bash
pytest -q
python -m compileall -q sdk tests
python -m build
```

The wheel exports only `ultradex_sdk`; the legacy MCP and Go CLI sources are not
included in the Python artifact.
