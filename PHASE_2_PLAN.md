# PHASE 2: Async Task Queue + v2 Endpoints

## Objective
Move execution from synchronous to async. Create v2 endpoints that return 202 Accepted immediately and dispatch work to Redis queue.

## Design

**Gateway Pattern:**
```
POST /api/v2/contacts/commands/analyze
  ↓
1. Validate authorization (Phase 5)
2. Create operation record (status: pending)
3. Enqueue job to Redis via ARQ
4. Return 202 Accepted with operation_id
  ↓
[Background Worker Process]
1. Fetch job from queue
2. Update operation: pending → running
3. Execute business logic
4. Update operation: running → completed/failed
5. Emit events (Phase 3)
```

## Architecture Changes

**New Dependencies:**
- `arq==0.25.0` - Async Redis Queue
- `redis==5.0.1` - Redis client

**New Docker Services:**
- `redis:7-alpine` - Task queue backend
- `worker` - Separate process running ARQ worker

**New Files:**
- `core/gateway.py` - Command dispatcher
- `core/workers.py` - ARQ worker configuration
- `core/tasks/` - Task implementations
- `api/routes/v2/` - v2 API endpoints

## Implementation Tasks

### Phase 2.1: Add Dependencies
- Add arq and redis to requirements.txt
- Update docker-compose.yml with Redis + worker services

### Phase 2.2: Create Gateway Service
- GatewayService.submit_command()
- Validates and dispatches to queue

### Phase 2.3: Create ARQ Worker Setup
- worker.py with WorkerSettings
- Task definitions in core/tasks/

### Phase 2.4: Create Task Implementations
- analyze_contacts_task()
- sync_contacts_task()

### Phase 2.5: Create v2 Endpoints
- POST /api/v2/contacts/commands/analyze
- POST /api/v2/contacts/commands/sync
- All return 202 Accepted

### Phase 2.6: Create v2 Operation Queries
- GET /api/v2/operations/{id}
- Same as v1 but new namespace

### Phase 2.7: Smoke Test
- Start Redis, worker, API
- Submit command, verify queue receives it
- Verify operation status transitions

## Estimated Time: 1.5-2 hours

## Files to Create
- `core/gateway.py`
- `core/workers.py`
- `core/tasks/__init__.py`
- `core/tasks/analyze.py`
- `core/tasks/sync.py`
- `api/routes/v2/__init__.py`
- `api/routes/v2/commands.py`
- `api/routes/v2/operations.py`

## Files to Modify
- `requirements.txt`
- `docker-compose.yml`
- `api/main.py`

## Success Criteria
- POST /api/v2/analyze returns 202 immediately
- Operation starts in 'pending', transitions to 'running'
- Worker processes queue and updates operation status
- Final status is 'completed' or 'failed'
- v1 endpoints still work (no breaking changes)
