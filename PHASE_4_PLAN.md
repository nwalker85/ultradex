# PHASE 4: GraphQL Query API

## Objective
Add read-only GraphQL endpoint for flexible queries.

## Design

**GraphQL Types:**
```graphql
type Operation {
  id: String!
  correlationId: String
  command: String!
  status: String!
  createdAt: DateTime!
  startedAt: DateTime
  completedAt: DateTime
  result: JSON
  error: String
  events: [OperationEvent!]!
}

type OperationEvent {
  id: Int!
  operationId: String!
  eventType: String!
  timestamp: DateTime!
  payload: JSON
}

type Query {
  operation(id: String!): Operation
  operations(limit: Int = 10, status: String): [Operation!]!
  events(operationId: String!): [OperationEvent!]!
}
```

**Features:**
- Read-only schema (no mutations)
- Query by ID, list with filters
- Nested event queries
- JSON payload access

## Implementation

### Phase 4.1: Add Dependencies
- strawberry-graphql[fastapi]==0.219.0

### Phase 4.2: Create GraphQL Schema
- Operation type
- OperationEvent type
- Query type with resolvers

### Phase 4.3: Add GraphQL Endpoint
- POST /api/graphql
- Include in FastAPI routes

### Phase 4.4: Smoke Test
- Query operations
- Query events

## Estimated Time: 60 minutes

## Files to Create
- `api/graphql/__init__.py`
- `api/graphql/schema.py`

## Files to Modify
- `requirements.txt`
- `api/main.py`

## Success Criteria
- GraphQL playground at /graphql
- Query { operation(id: "...") { id status } }
- Query { operations { id command status } }
- Nested event queries work
