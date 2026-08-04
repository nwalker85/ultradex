"""Authenticated REST command boundary for the job-search domain."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core import (
    IdempotencyConflictError,
    JobSearchCommandRequest,
    JobSearchDispatchError,
    JobSearchGatewayService,
    JobSearchTaskPublisher,
    ReceiptIssuer,
    get_db,
)

from ...auth import AuthenticatedPrincipal, require_command_principal
from ...dependencies import get_jobsearch_publisher, get_receipt_issuer
from .commands import (
    CONTRACT_HANDLE_RESPONSE,
    _contract_handle,
    _submission_response,
)


router = APIRouter()


@router.post(
    "/job-search/commands/{command_name}",
    status_code=202,
    response_model=None,
    responses=CONTRACT_HANDLE_RESPONSE,
)
async def submit_jobsearch_command(
    command_name: str,
    parameters: dict[str, object] = Body(...),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
    ),
    delegation_id: str | None = Header(
        default=None,
        alias="X-Delegation-Id",
    ),
    correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-Id",
    ),
    principal: AuthenticatedPrincipal = Depends(require_command_principal),
    db: Session = Depends(get_db),
    publisher: JobSearchTaskPublisher = Depends(get_jobsearch_publisher),
    receipt_issuer: ReceiptIssuer = Depends(get_receipt_issuer),
) -> dict[str, object] | JSONResponse:
    """Accept a canonical command and return its governed operation handle."""
    try:
        operation = await JobSearchGatewayService(
            publisher,
            receipt_issuer,
        ).submit_command(
            db,
            JobSearchCommandRequest(
                command=command_name,
                parameters=parameters,
                actor_id=principal.subject,
                idempotency_key=idempotency_key,
                delegation_id=delegation_id,
                correlation_id=correlation_id,
            ),
        )
        return _submission_response(operation)
    except IdempotencyConflictError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": "Idempotency key is bound to another command envelope",
            },
        )
    except JobSearchDispatchError as error:
        return JSONResponse(
            status_code=503,
            content=_contract_handle(error.operation),
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "command_authority_refused",
                "message": "Command authority refused",
            },
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_command_contract",
                "message": str(error),
            },
        )
