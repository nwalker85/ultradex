"""Fail-closed authentication and scope enforcement for private surfaces."""

from dataclasses import dataclass
import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


READ_SCOPE = "read"
COMMAND_SCOPE = "command"
DELEGATION_ADMIN_SCOPE = "delegation-admin"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    scopes: frozenset[str]


def validate_auth_configuration() -> None:
    """Refuse to start if the private operator credential is not configured."""
    missing = [
        name
        for name in ("ULTRADEX_API_TOKEN", "ULTRADEX_OPERATOR_ID")
        if not os.getenv(name)
    ]
    if missing:
        raise ValueError(f"Missing private auth configuration: {', '.join(missing)}")

    command_token = os.getenv("ULTRADEX_COMMAND_TOKEN")
    command_id = os.getenv("ULTRADEX_COMMAND_ID")
    if bool(command_token) != bool(command_id):
        missing_name = (
            "ULTRADEX_COMMAND_ID" if command_token else "ULTRADEX_COMMAND_TOKEN"
        )
        raise ValueError(
            f"Incomplete command auth configuration: missing {missing_name}"
        )

    other_role_tokens = (
        ("ULTRADEX_API_TOKEN", os.getenv("ULTRADEX_API_TOKEN")),
        ("ULTRADEX_READ_TOKEN", os.getenv("ULTRADEX_READ_TOKEN")),
    )
    for other_name, other_value in other_role_tokens:
        if (
            command_token
            and other_value
            and secrets.compare_digest(command_token, other_value)
        ):
            raise ValueError(
                "Conflicting auth token configuration: "
                f"ULTRADEX_COMMAND_TOKEN and {other_name} must differ"
            )


def authenticate_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedPrincipal:
    """Validate a bearer token and derive identity server-side."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplied = credentials.credentials
    operator_token = os.getenv("ULTRADEX_API_TOKEN")
    operator_id = os.getenv("ULTRADEX_OPERATOR_ID")
    if operator_token and operator_id and secrets.compare_digest(supplied, operator_token):
        return AuthenticatedPrincipal(
            subject=operator_id,
            scopes=frozenset({READ_SCOPE, COMMAND_SCOPE, DELEGATION_ADMIN_SCOPE}),
        )

    command_token = os.getenv("ULTRADEX_COMMAND_TOKEN")
    command_id = os.getenv("ULTRADEX_COMMAND_ID")
    if command_token and command_id and secrets.compare_digest(supplied, command_token):
        return AuthenticatedPrincipal(
            subject=command_id,
            scopes=frozenset({READ_SCOPE, COMMAND_SCOPE}),
        )

    read_token = os.getenv("ULTRADEX_READ_TOKEN")
    read_id = os.getenv("ULTRADEX_READ_ID")
    if read_token and read_id and secrets.compare_digest(supplied, read_token):
        return AuthenticatedPrincipal(
            subject=read_id,
            scopes=frozenset({READ_SCOPE}),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid bearer credential",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _require_scope(
    principal: AuthenticatedPrincipal,
    scope: str,
) -> AuthenticatedPrincipal:
    if scope not in principal.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Credential lacks required scope: {scope}",
        )
    return principal


def require_read_principal(
    principal: AuthenticatedPrincipal = Depends(authenticate_principal),
) -> AuthenticatedPrincipal:
    return _require_scope(principal, READ_SCOPE)


def require_command_principal(
    principal: AuthenticatedPrincipal = Depends(authenticate_principal),
) -> AuthenticatedPrincipal:
    return _require_scope(principal, COMMAND_SCOPE)


def require_delegation_admin_principal(
    principal: AuthenticatedPrincipal = Depends(authenticate_principal),
) -> AuthenticatedPrincipal:
    return _require_scope(principal, DELEGATION_ADMIN_SCOPE)
