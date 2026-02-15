# PHASE 5: ANP Delegation + Governance

## Objective
Add delegation-based authorization and idempotency guarantees.

## Design

**Delegation Model:**
```
DelegationDB:
  - id (UUID)
  - delegator (user_id)
  - delegatee (user_id/service_id)
  - allowed_actions (array: "analyze", "sync")
  - allowed_resources (array: "*" or specific IDs)
  - expires_at (datetime)
  - revoked_at (datetime, null = active)
```

**Idempotency:**
```
IdempotencyKeyDB:
  - key (string, unique)
  - operation_id (foreign key)
  - created_at (datetime)
  - expires_at (datetime, +24 hours)
```

**Gateway Validation Flow:**
```
POST /api/v2/contacts/commands/analyze
+ Header: X-Delegation-ID: skuld-abc123
+ Header: Idempotency-Key: uuid-abc

Gateway:
  1. Check idempotency key exists → return cached operation_id
  2. Validate delegation: delegatee=actor, action in allowed_actions
  3. Create operation
  4. Store idempotency mapping
  5. Enqueue job
  6. Return 202 + operation_id
```

## Implementation

### Phase 5.1: Create Delegation Models
- DelegationDB SQLAlchemy model
- IdempotencyKeyDB model
- Create tables

### Phase 5.2: Create Authorization Service
- validate_delegation()
- get_delegation()
- check_authorization()

### Phase 5.3: Create Idempotency Service
- record_idempotency()
- get_cached_operation()
- cleanup_expired_keys()

### Phase 5.4: Integrate with Gateway
- Check idempotency before dispatch
- Validate delegation
- Return cached operation if exists

### Phase 5.5: Add Delegation Endpoints
- POST /api/v2/delegations (create)
- GET /api/v2/delegations (list)
- DELETE /api/v2/delegations/{id} (revoke)

### Phase 5.6: Update v1 Endpoints
- Add deprecation headers
- Log warnings

### Phase 5.7: Create Python SDK
- Wrapper around v2 API
- Handles polling, retries
- Type hints

## Files to Create
- `core/delegation_service.py`
- `core/idempotency_service.py`
- `api/routes/v2/delegations.py`
- `sdk/ultradex_sdk.py`

## Estimated Time: 90 minutes

## Success Criteria
- Delegation validation works
- Idempotency prevents duplicates
- v1 has deprecation headers
- SDK polling complete
