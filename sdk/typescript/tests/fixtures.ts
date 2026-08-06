export const syntheticHealthResponse = {
  status: "ok",
  timestamp: "2026-07-29T12:00:00",
} as const;

export const syntheticReadinessResponse = {
  ready: true,
  timestamp: "2026-07-29T12:00:01",
} as const;

export const syntheticProjectionFreshness = {
  sourceEventId: "event-synthetic-001",
  sourceEventPosition: "SYNTHETIC:1",
  projectedAt: "2026-07-29T12:00:02+00:00",
  lagMs: 12,
  status: "fresh",
} as const;

export const syntheticContractHandleResponse = {
  contract_id: "contract-synthetic-001",
  operation_id: "operation-synthetic-001",
  status: "accepted",
  submitted_at: "2026-07-29T12:00:03+00:00",
  correlation_id: "correlation-synthetic-001",
  refusal_code: null,
  refusal_reason: null,
  expires_at: "2026-07-29T12:15:03+00:00",
  status_url: "/operations/operation-synthetic-001",
  events_url: "/operations/operation-synthetic-001/events",
} as const;

export const syntheticRefusedContractHandleResponse = {
  contract_id: "contract-synthetic-refused-001",
  operation_id: "operation-synthetic-refused-001",
  status: "refused",
  submitted_at: "2026-07-29T12:00:05+00:00",
  correlation_id: "correlation-synthetic-refused-001",
  refusal_code: "synthetic_policy_denied",
  refusal_reason: "Synthetic policy did not authorize this operation",
  expires_at: null,
  status_url: "/operations/operation-synthetic-refused-001",
  events_url: "/operations/operation-synthetic-refused-001/events",
} as const;

export const syntheticOperation = {
  id: "operation-synthetic-001",
  correlationId: "correlation-synthetic-001",
  command: "synthetic.inspect",
  status: "running",
  createdAt: "2026-07-29T12:00:03+00:00",
  startedAt: "2026-07-29T12:00:04+00:00",
  completedAt: null,
  result: null,
  error: null,
  freshness: syntheticProjectionFreshness,
} as const;

export const syntheticLifecycleEvent = {
  id: 101,
  operationId: "operation-synthetic-001",
  eventType: "synthetic.operation.accepted",
  timestamp: "2026-07-29T12:00:04+00:00",
  payload: {
    classification: "synthetic",
    lifecycleState: "accepted",
  },
} as const;

export const syntheticGraphQLData = {
  operation: {
    id: "operation-synthetic-001",
  },
} as const;

export const syntheticGraphQLErrors = {
  data: null,
  errors: [
    {
      message: "Synthetic operation is unavailable",
      path: ["operation"],
      extensions: {
        code: "SYNTHETIC_UNAVAILABLE",
      },
    },
  ],
} as const;

export const syntheticOpportunityPage = {
  items: [
    {
      opportunityId: "opportunity-synthetic-001",
      employer: "Synthetic Systems",
      title: "Platform Engineer",
      location: "Remote",
      roleFamily: "Engineering",
      status: "qualified",
      fitScore: 91,
      fitExplanation: "Strong synthetic platform fit.",
      riskFlags: ["compensation-unverified"],
      evidenceRefs: [
        {
          evidenceId: "evidence-synthetic-001",
          sourceKind: "manual",
          sourceRef: "source-synthetic-001",
          classification: "private",
          observedAt: "2026-07-29T12:00:00+00:00",
          commitment:
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          redactedSummary: "Synthetic public role metadata reviewed.",
        },
      ],
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:59:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-opportunities",
    sourceEventPosition: "SYNTHETIC:2",
    projectedAt: "2026-07-29T12:00:03+00:00",
    lagMs: 13,
    status: "stale",
  },
  nextCursor: "opportunity-synthetic-001",
} as const;

export const syntheticApplicationPage = {
  items: [
    {
      applicationId: "application-synthetic-001",
      opportunityId: "opportunity-synthetic-001",
      status: "applied",
      stageHistory: [
        {
          status: "draft",
          occurredAt: "2026-07-29T11:00:00+00:00",
          evidenceRef: "evidence-synthetic-001",
        },
        {
          status: "applied",
          occurredAt: "2026-07-29T12:00:00+00:00",
          evidenceRef: "evidence-synthetic-002",
        },
      ],
      artifactRefs: ["artifact-synthetic-resume"],
      nextAction: "Synthetic follow-up",
      nextActionAt: "2026-07-30T12:00:00+00:00",
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:00:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-applications",
    sourceEventPosition: "SYNTHETIC:3",
    projectedAt: "2026-07-29T12:00:04+00:00",
    lagMs: 14,
    status: "fresh",
  },
  nextCursor: null,
} as const;

export const syntheticRelationshipPage = {
  items: [
    {
      relationshipId: "relationship-synthetic-001",
      opportunityId: "opportunity-synthetic-001",
      dexContactRef: "dex-contact-synthetic-001",
      relevanceScore: 88,
      relevanceSummary: "Synthetic professional relationship.",
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:30:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-relationships",
    sourceEventPosition: "SYNTHETIC:4",
    projectedAt: "2026-07-29T12:00:05+00:00",
    lagMs: 15,
    status: "fresh",
  },
  nextCursor: "relationship-synthetic-001",
} as const;

export const syntheticOutreachPage = {
  items: [
    {
      outreachId: "outreach-synthetic-001",
      opportunityId: "opportunity-synthetic-001",
      relationshipId: "relationship-synthetic-001",
      status: "approved",
      channel: "gmail",
      messageCommitment:
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      approvalContractId: "approval-synthetic-001",
      sentEvidenceRef: null,
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:45:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-outreach",
    sourceEventPosition: "SYNTHETIC:5",
    projectedAt: "2026-07-29T12:00:06+00:00",
    lagMs: 16,
    status: "replaying",
  },
  nextCursor: null,
} as const;

export const syntheticCompletedOperation = {
  id: "operation-synthetic-completed-001",
  correlationId: "correlation-synthetic-completed-001",
  command: "opportunities.create",
  status: "completed",
  createdAt: "2026-07-29T12:00:03+00:00",
  startedAt: "2026-07-29T12:00:04+00:00",
  completedAt: "2026-07-29T12:00:05+00:00",
  result: {
    opportunity_id: "opportunity-synthetic-001",
  },
  error: null,
  freshness: null,
} as const;

export const syntheticApprovalEvidence = {
  approvalId: "approval-synthetic-001",
  outreachId: "outreach-synthetic-001",
  messageCommitment:
    "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  channel: "gmail",
  approvedBy: "operator:synthetic",
  issuedAt: "2026-07-29T12:00:00+00:00",
  expiresAt: "2026-07-30T12:00:00+00:00",
  status: "approved",
} as const;

export const syntheticExecutionReceiptPayload = {
  contract_version: "accountability.v1",
  receipt_id: "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
  event_id: "opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
  stream_pairwise_id: "pairwise:v1:SSSSSSSSSSSSSSSSSSSSSS",
  sequence: 1,
  subject_pairwise_id: "pairwise:v1:UUUUUUUUUUUUUUUUUUUUUU",
  tenant_scope: {
    scheme: "hmac_sha256_v1",
    purpose: "jobsearch_operation",
    digest:
      "sha256:1111111111111111111111111111111111111111111111111111111111111111",
  },
  purpose: "jobsearch_operation",
  request_id: "opaque:v1:QQQQQQQQQQQQQQQQQQQQQQ",
  idempotency_key: "opaque:v1:IIIIIIIIIIIIIIIIIIIIII",
  action_commitment: {
    scheme: "hmac_sha256_v1",
    purpose: "jobsearch_operation",
    digest:
      "sha256:2222222222222222222222222222222222222222222222222222222222222222",
  },
  execution_id: "opaque:v1:XXXXXXXXXXXXXXXXXXXXXX",
  executor_pairwise_id: "pairwise:v1:ZZZZZZZZZZZZZZZZZZZZZZ",
  status: "succeeded",
  started_at: "2026-07-29T12:00:00.000Z",
  completed_at: "2026-07-29T12:01:00.000Z",
  result_commitment: {
    scheme: "hmac_sha256_v1",
    purpose: "jobsearch_operation",
    digest:
      "sha256:3333333333333333333333333333333333333333333333333333333333333333",
  },
  reason_code: null,
  daml_transaction: null,
  signature: {
    algorithm: "ed25519",
    key_id: "pairwise:v1:KKKKKKKKKKKKKKKKKKKKKK",
    signature:
      "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  },
} as const;

export const syntheticExecutionReceiptEvidence = {
  receiptId: "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
  operationId: "operation-synthetic-completed-001",
  eventId: "opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
  status: "succeeded",
  reasonCode: null,
  payload: syntheticExecutionReceiptPayload,
  receiptHash:
    "sha256:e18c64598f2b5ed18116c8a00403bba04bb3f219d222377880a66fa56683d145",
  createdAt: "2026-07-29T12:01:00+00:00",
  completedAt: "2026-07-29T12:01:00+00:00",
  proofStatus: "server-recorded",
} as const;
