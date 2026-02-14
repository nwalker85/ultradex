# PHASE 3: Event Sourcing + Audit Trail

## Objective
Add append-only event log for every operation state change. Enable audit trail and compliance.

## Design

**Event Types:**
```
- operation.accepted: Gateway accepted the command
- task.started: Worker began execution
- task.progress: Optional intermediate progress (Phase 3+)
- task.completed: Work finished successfully
- task.failed: Execution encountered error
```

**Event Storage:**
```
CREATE TABLE operation_events (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR(36) NOT NULL FOREIGN KEY,
    event_type VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    payload JSON,
    FOREIGN KEY (operation_id) REFERENCES operations(id)
);
```

## Implementation

### Phase 3.1: Create Event Models & Enums
- EventType enum
- OperationEventDB SQLAlchemy model
- OperationEvent Pydantic model

### Phase 3.2: Create Event Producer Service
- emit_event() method
- Appends to operation_events table

### Phase 3.3: Integrate with Gateway
- Emit `operation.accepted` when command received

### Phase 3.4: Integrate with Tasks
- Emit `task.started` when execution begins
- Emit `task.completed` on success
- Emit `task.failed` on error

### Phase 3.5: Add Event Query Endpoint
- GET /api/v1/operations/{id}/events
- Returns chronological event log

### Phase 3.6: Smoke Test
- Verify events are recorded
- Query events for operation

## Files to Create
- `core/events/schema.py` - Event models
- `core/events/producer.py` - Event emission

## Files to Modify
- `core/models.py` - Add OperationEventDB
- `core/__init__.py` - Export event classes
- `core/gateway.py` - Emit operation.accepted
- `core/tasks/analyze.py` - Emit events
- `core/tasks/sync.py` - Emit events
- `api/routes/operations.py` - Add events endpoint

## Estimated Time: 45 minutes
