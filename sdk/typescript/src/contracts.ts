import { z } from "zod";

const nonEmptyStringSchema = z.string().min(1);
const isoTimestampSchema = z.string().refine(
  (value) =>
    /^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/u.test(value) &&
    !Number.isNaN(Date.parse(value)),
  "Expected an ISO 8601 timestamp with timezone",
);
const apiTimestampSchema = z.string().refine(
  (value) =>
    /^\d{4}-\d{2}-\d{2}T.+$/u.test(value) && !Number.isNaN(Date.parse(value)),
  "Expected an ISO 8601 timestamp",
);
const wholeMinuteTimestampSchema = z.string().refine(
  (value) =>
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\.000Z$/u.test(value) &&
    !Number.isNaN(Date.parse(value)),
  "Expected a whole-minute RFC 3339 UTC timestamp",
);
const sha256DigestSchema = z.string().regex(/^sha256:[0-9a-f]{64}$/u);
const opaqueIdSchema = z
  .string()
  .regex(/^opaque:v1:[A-Za-z0-9_-]{22,86}$/u);
const pairwiseIdSchema = z
  .string()
  .regex(/^pairwise:v1:[A-Za-z0-9_-]{22,86}$/u);

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | readonly JsonValue[]
  | { readonly [key: string]: JsonValue };

const jsonValueSchema: z.ZodType<JsonValue> = z.lazy(() =>
  z.union([
    z.string(),
    z.number(),
    z.boolean(),
    z.null(),
    z.array(jsonValueSchema),
    z.record(z.string(), jsonValueSchema),
  ]),
);

export const contractStatusSchema = z.enum([
  "accepted",
  "refused",
  "pending",
  "running",
  "partial",
  "succeeded",
  "failed",
  "cancelled",
  "compensating",
  "expired",
  "revoked",
  "unverifiable",
]);

export const projectionStatusSchema = z.enum([
  "fresh",
  "stale",
  "replaying",
  "unavailable",
]);

export const opportunityStatusSchema = z.enum([
  "discovered",
  "qualified",
  "watching",
  "archived",
]);

export const applicationStatusSchema = z.enum([
  "draft",
  "applied",
  "screening",
  "interviewing",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
  "closed",
]);

export const outreachStatusSchema = z.enum([
  "draft",
  "pending_approval",
  "approved",
  "sent",
  "failed",
  "cancelled",
]);

export const operationStatusSchema = z.enum([
  "pending",
  "running",
  "completed",
  "failed",
  "refused",
]);

export const JOB_SEARCH_COMMAND_NAMES = [
  "sources.ingest",
  "opportunities.create",
  "opportunities.score",
  "applications.transition",
  "relationships.sync",
  "outreach.prepare",
  "outreach.approve",
  "outreach.send",
  "evidence.export",
] as const;

export const jobSearchCommandNameSchema = z.enum(
  JOB_SEARCH_COMMAND_NAMES,
);

const jobSearchSourceKindSchema = z.enum([
  "gmail",
  "linkedin",
  "dex",
  "manual",
  "web",
]);
const outreachChannelSchema = z.enum(["gmail", "linkedin", "manual"]);
const opaqueReferenceSchema = (prefix: string) =>
  z.string().regex(
    new RegExp(`^${prefix}[-:][A-Za-z0-9._:-]{1,120}$`, "u"),
    `Expected an opaque ${prefix} reference`,
  );

export const sourcesIngestParametersSchema = z
  .object({
    sourceKind: jobSearchSourceKindSchema,
    sourceRef: nonEmptyStringSchema,
    observedAt: isoTimestampSchema,
  })
  .strict()
  .superRefine((value, context) => {
    if (
      !opaqueReferenceSchema(value.sourceKind).safeParse(value.sourceRef)
        .success
    ) {
      context.addIssue({
        code: "custom",
        message: `Expected an opaque ${value.sourceKind} reference`,
        path: ["sourceRef"],
      });
    }
  });

export const opportunityCreateParametersSchema = z
  .object({
    employer: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    sourceEvidenceId: opaqueReferenceSchema("evidence"),
  })
  .strict();

export const opportunityScoreParametersSchema = z
  .object({
    opportunityId: nonEmptyStringSchema,
    lens: nonEmptyStringSchema,
  })
  .strict();

export const applicationTransitionParametersSchema = z
  .object({
    applicationId: nonEmptyStringSchema,
    status: applicationStatusSchema,
    occurredAt: isoTimestampSchema,
  })
  .strict();

export const relationshipSyncParametersSchema = z
  .object({
    opportunityId: nonEmptyStringSchema,
    dexContactRef: opaqueReferenceSchema("dex"),
  })
  .strict();

export const outreachPrepareParametersSchema = z
  .object({
    opportunityId: nonEmptyStringSchema,
    channel: outreachChannelSchema,
    messageCommitment: sha256DigestSchema,
    relationshipId: nonEmptyStringSchema.optional(),
  })
  .strict();

export const outreachApproveParametersSchema = z
  .object({
    outreachId: nonEmptyStringSchema,
    messageCommitment: sha256DigestSchema,
  })
  .strict();

export const outreachSendParametersSchema = z
  .object({
    outreachId: nonEmptyStringSchema,
    approvalContractId: nonEmptyStringSchema,
    messageCommitment: sha256DigestSchema,
    channel: outreachChannelSchema,
  })
  .strict();

export const evidenceExportParametersSchema = z
  .object({
    subjectType: nonEmptyStringSchema,
    subjectId: nonEmptyStringSchema,
    profile: z.literal("accountability.v1"),
  })
  .strict();

export const jobSearchCommandSchema = z.discriminatedUnion("commandName", [
  z
    .object({
      commandName: z.literal("sources.ingest"),
      parameters: sourcesIngestParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("opportunities.create"),
      parameters: opportunityCreateParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("opportunities.score"),
      parameters: opportunityScoreParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("applications.transition"),
      parameters: applicationTransitionParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("relationships.sync"),
      parameters: relationshipSyncParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("outreach.prepare"),
      parameters: outreachPrepareParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("outreach.approve"),
      parameters: outreachApproveParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("outreach.send"),
      parameters: outreachSendParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("evidence.export"),
      parameters: evidenceExportParametersSchema,
    })
    .strict(),
]);

export const healthStatusSchema = z
  .object({
    status: z.literal("ok"),
    timestamp: apiTimestampSchema,
  })
  .strict();

export const readinessStatusSchema = z
  .object({
    ready: z.boolean(),
    timestamp: apiTimestampSchema,
  })
  .strict();

export const projectionFreshnessSchema = z
  .object({
    sourceEventId: nonEmptyStringSchema,
    sourceEventPosition: nonEmptyStringSchema,
    projectedAt: isoTimestampSchema,
    lagMs: z.number().nonnegative(),
    status: projectionStatusSchema,
  })
  .strict();

export const evidenceReferenceSchema = z
  .object({
    evidenceId: nonEmptyStringSchema,
    sourceKind: z.enum(["gmail", "linkedin", "dex", "manual", "web"]),
    sourceRef: nonEmptyStringSchema,
    classification: nonEmptyStringSchema,
    observedAt: isoTimestampSchema,
    commitment: sha256DigestSchema,
    redactedSummary: nonEmptyStringSchema.max(240),
  })
  .strict();

export const opportunitySchema = z
  .object({
    opportunityId: nonEmptyStringSchema,
    employer: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    location: nonEmptyStringSchema.nullable(),
    roleFamily: nonEmptyStringSchema.nullable(),
    status: opportunityStatusSchema,
    fitScore: z.number().min(0).max(100).nullable(),
    fitExplanation: nonEmptyStringSchema.nullable(),
    riskFlags: z.array(nonEmptyStringSchema),
    evidenceRefs: z.array(evidenceReferenceSchema),
    freshness: projectionFreshnessSchema,
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const applicationStageSchema = z
  .object({
    status: applicationStatusSchema,
    occurredAt: isoTimestampSchema,
    evidenceRef: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const applicationSchema = z
  .object({
    applicationId: nonEmptyStringSchema,
    opportunityId: nonEmptyStringSchema,
    status: applicationStatusSchema,
    stageHistory: z.array(applicationStageSchema),
    artifactRefs: z.array(nonEmptyStringSchema),
    nextAction: nonEmptyStringSchema.nullable(),
    nextActionAt: isoTimestampSchema.nullable(),
    freshness: projectionFreshnessSchema,
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const relationshipSchema = z
  .object({
    relationshipId: nonEmptyStringSchema,
    opportunityId: nonEmptyStringSchema,
    dexContactRef: nonEmptyStringSchema,
    relevanceScore: z.number().min(0).max(100).nullable(),
    relevanceSummary: nonEmptyStringSchema.nullable(),
    freshness: projectionFreshnessSchema,
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const outreachSchema = z
  .object({
    outreachId: nonEmptyStringSchema,
    opportunityId: nonEmptyStringSchema,
    relationshipId: nonEmptyStringSchema.nullable(),
    status: outreachStatusSchema,
    channel: z.enum(["gmail", "linkedin", "manual"]),
    messageCommitment: sha256DigestSchema,
    approvalContractId: nonEmptyStringSchema.nullable(),
    sentEvidenceRef: nonEmptyStringSchema.nullable(),
    freshness: projectionFreshnessSchema,
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const opportunityPageSchema = z
  .object({
    items: z.array(opportunitySchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const applicationPageSchema = z
  .object({
    items: z.array(applicationSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const relationshipPageSchema = z
  .object({
    items: z.array(relationshipSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const outreachPageSchema = z
  .object({
    items: z.array(outreachSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const operationSchema = z
  .object({
    id: nonEmptyStringSchema,
    correlationId: nonEmptyStringSchema.nullable(),
    command: nonEmptyStringSchema,
    status: operationStatusSchema,
    createdAt: isoTimestampSchema,
    startedAt: isoTimestampSchema.nullable(),
    completedAt: isoTimestampSchema.nullable(),
    result: jsonValueSchema,
    error: z.string().min(1).nullable(),
    freshness: projectionFreshnessSchema.nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    const terminal =
      value.status === "completed" ||
      value.status === "failed" ||
      value.status === "refused";
    if (terminal && value.completedAt === null) {
      context.addIssue({
        code: "custom",
        message: "Terminal operations require completedAt",
        path: ["completedAt"],
      });
    }
    if (!terminal && value.completedAt !== null) {
      context.addIssue({
        code: "custom",
        message: "Non-terminal operations cannot have completedAt",
        path: ["completedAt"],
      });
    }
  });

export const operationLifecycleEventSchema = z
  .object({
    id: z.number().int().positive(),
    operationId: nonEmptyStringSchema,
    eventType: nonEmptyStringSchema,
    timestamp: isoTimestampSchema,
    payload: jsonValueSchema,
  })
  .strict();

export const approvalEvidenceSchema = z
  .object({
    approvalId: nonEmptyStringSchema,
    outreachId: nonEmptyStringSchema,
    messageCommitment: sha256DigestSchema,
    channel: z.enum(["gmail", "linkedin", "manual"]),
    approvedBy: nonEmptyStringSchema,
    issuedAt: isoTimestampSchema,
    expiresAt: isoTimestampSchema,
    status: z.enum(["approved", "expired", "revoked"]),
  })
  .strict()
  .superRefine((value, context) => {
    if (Date.parse(value.expiresAt) <= Date.parse(value.issuedAt)) {
      context.addIssue({
        code: "custom",
        message: "Approval expiry must follow issuance",
        path: ["expiresAt"],
      });
    }
  });

const purposeBoundCommitmentSchema = z
  .object({
    scheme: z.enum([
      "hmac_sha256_v1",
      "sha256_high_entropy_ciphertext_v1",
    ]),
    purpose: nonEmptyStringSchema,
    digest: sha256DigestSchema,
  })
  .strict();

const signatureEnvelopeSchema = z
  .object({
    algorithm: z.literal("ed25519"),
    key_id: pairwiseIdSchema,
    signature: z.string().regex(/^[A-Za-z0-9_-]{86}$/u),
  })
  .strict();

const chainIdentitySchema = z
  .object({
    ledger_family: z.literal("daml"),
    network_commitment: purposeBoundCommitmentSchema,
    ledger_pairwise_id: pairwiseIdSchema,
    participant_pairwise_id: pairwiseIdSchema,
  })
  .strict();

const damlTransactionSchema = z
  .object({
    contract_version: z.literal("accountability.v1"),
    chain_identity: chainIdentitySchema,
    command_id: nonEmptyStringSchema,
    transaction_id: nonEmptyStringSchema.nullable(),
    status: z.enum(["submitted", "committed", "rejected"]),
    submitted_at: wholeMinuteTimestampSchema,
    recorded_at: wholeMinuteTimestampSchema.nullable(),
    rejection_code: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const executionReceiptPayloadSchema = z
  .object({
    contract_version: z.literal("accountability.v1"),
    receipt_id: opaqueIdSchema,
    event_id: opaqueIdSchema,
    stream_pairwise_id: pairwiseIdSchema,
    sequence: z.number().int().nonnegative(),
    subject_pairwise_id: pairwiseIdSchema,
    tenant_scope: purposeBoundCommitmentSchema,
    purpose: nonEmptyStringSchema,
    request_id: opaqueIdSchema,
    idempotency_key: opaqueIdSchema,
    action_commitment: purposeBoundCommitmentSchema,
    execution_id: opaqueIdSchema,
    executor_pairwise_id: pairwiseIdSchema,
    status: z.enum(["succeeded", "failed", "refused"]),
    started_at: wholeMinuteTimestampSchema,
    completed_at: wholeMinuteTimestampSchema,
    result_commitment: purposeBoundCommitmentSchema.nullable(),
    reason_code: z
      .enum([
        "policy_denied",
        "executor_failure",
        "authority_expired",
        "safety_refusal",
      ])
      .nullable(),
    daml_transaction: damlTransactionSchema.nullable(),
    signature: signatureEnvelopeSchema,
  })
  .strict()
  .superRefine((value, context) => {
    if (Date.parse(value.completed_at) < Date.parse(value.started_at)) {
      context.addIssue({
        code: "custom",
        message: "Receipt completion cannot precede start",
        path: ["completed_at"],
      });
    }
    if (
      value.status === "succeeded" &&
      (value.result_commitment === null || value.reason_code !== null)
    ) {
      context.addIssue({
        code: "custom",
        message:
          "Successful receipts require result_commitment and no reason_code",
        path: ["status"],
      });
    }
    if (value.status !== "succeeded" && value.reason_code === null) {
      context.addIssue({
        code: "custom",
        message: "Failed or refused receipts require reason_code",
        path: ["reason_code"],
      });
    }
  });

export const executionReceiptEvidenceSchema = z
  .object({
    receiptId: opaqueIdSchema,
    operationId: nonEmptyStringSchema,
    eventId: opaqueIdSchema,
    status: z.enum(["succeeded", "failed", "refused"]),
    reasonCode: z
      .enum([
        "policy_denied",
        "executor_failure",
        "authority_expired",
        "safety_refusal",
      ])
      .nullable(),
    payload: executionReceiptPayloadSchema,
    receiptHash: sha256DigestSchema,
    createdAt: isoTimestampSchema,
    completedAt: isoTimestampSchema,
    proofStatus: z.literal("server-recorded"),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.receiptId !== value.payload.receipt_id ||
      value.eventId !== value.payload.event_id ||
      value.status !== value.payload.status ||
      value.reasonCode !== value.payload.reason_code
    ) {
      context.addIssue({
        code: "custom",
        message: "Receipt evidence does not match its signed payload",
        path: ["payload"],
      });
    }
    if (
      Date.parse(value.completedAt) !== Date.parse(value.payload.completed_at)
    ) {
      context.addIssue({
        code: "custom",
        message:
          "Receipt completion does not match its signed payload instant",
        path: ["completedAt"],
      });
    }
  });

const contractHandleWireShape = {
  contract_id: nonEmptyStringSchema,
  operation_id: nonEmptyStringSchema,
  submitted_at: isoTimestampSchema,
  correlation_id: nonEmptyStringSchema,
  expires_at: isoTimestampSchema.nullable().optional(),
  status_url: nonEmptyStringSchema.nullable().optional(),
  events_url: nonEmptyStringSchema.nullable().optional(),
};

const nonRefusedContractStatusSchema = z.enum([
  "accepted",
  "pending",
  "running",
  "partial",
  "succeeded",
  "failed",
  "cancelled",
  "compensating",
  "expired",
  "revoked",
  "unverifiable",
]);

const refusedContractHandleSchema = z
  .object({
    ...contractHandleWireShape,
    status: z.literal("refused"),
    refusal_code: nonEmptyStringSchema,
    refusal_reason: nonEmptyStringSchema,
  })
  .strict()
  .transform((value) => ({
    contractId: value.contract_id,
    operationId: value.operation_id,
    status: value.status,
    submittedAt: value.submitted_at,
    correlationId: value.correlation_id,
    refusalCode: value.refusal_code,
    refusalReason: value.refusal_reason,
    ...(value.expires_at === undefined
      ? {}
      : { expiresAt: value.expires_at }),
    ...(value.status_url === undefined ? {} : { statusUrl: value.status_url }),
    ...(value.events_url === undefined ? {} : { eventsUrl: value.events_url }),
  }));

const nonRefusedContractHandleSchema = z
  .object({
    ...contractHandleWireShape,
    status: nonRefusedContractStatusSchema,
    refusal_code: z.null().optional(),
    refusal_reason: z.null().optional(),
  })
  .strict()
  .transform((value) => ({
    contractId: value.contract_id,
    operationId: value.operation_id,
    status: value.status,
    submittedAt: value.submitted_at,
    correlationId: value.correlation_id,
    ...(value.refusal_code === undefined
      ? {}
      : { refusalCode: value.refusal_code }),
    ...(value.refusal_reason === undefined
      ? {}
      : { refusalReason: value.refusal_reason }),
    ...(value.expires_at === undefined
      ? {}
      : { expiresAt: value.expires_at }),
    ...(value.status_url === undefined ? {} : { statusUrl: value.status_url }),
    ...(value.events_url === undefined ? {} : { eventsUrl: value.events_url }),
  }));

export const contractHandleResponseSchema = z.union([
  refusedContractHandleSchema,
  nonRefusedContractHandleSchema,
]);

export type ContractStatus = z.infer<typeof contractStatusSchema>;
export type ProjectionStatus = z.infer<typeof projectionStatusSchema>;
export type OpportunityStatus = z.infer<typeof opportunityStatusSchema>;
export type ApplicationStatus = z.infer<typeof applicationStatusSchema>;
export type OutreachStatus = z.infer<typeof outreachStatusSchema>;
export type OperationStatus = z.infer<typeof operationStatusSchema>;
export type JobSearchCommandName = z.infer<
  typeof jobSearchCommandNameSchema
>;
export type SourcesIngestParameters = z.infer<
  typeof sourcesIngestParametersSchema
>;
export type OpportunityCreateParameters = z.infer<
  typeof opportunityCreateParametersSchema
>;
export type OpportunityScoreParameters = z.infer<
  typeof opportunityScoreParametersSchema
>;
export type ApplicationTransitionParameters = z.infer<
  typeof applicationTransitionParametersSchema
>;
export type RelationshipSyncParameters = z.infer<
  typeof relationshipSyncParametersSchema
>;
export type OutreachPrepareParameters = z.infer<
  typeof outreachPrepareParametersSchema
>;
export type OutreachApproveParameters = z.infer<
  typeof outreachApproveParametersSchema
>;
export type OutreachSendParameters = z.infer<
  typeof outreachSendParametersSchema
>;
export type EvidenceExportParameters = z.infer<
  typeof evidenceExportParametersSchema
>;
export type JobSearchCommand = z.infer<typeof jobSearchCommandSchema>;
export type HealthStatus = z.infer<typeof healthStatusSchema>;
export type ReadinessStatus = z.infer<typeof readinessStatusSchema>;
export type ProjectionFreshness = z.infer<typeof projectionFreshnessSchema>;
export type EvidenceReference = z.infer<typeof evidenceReferenceSchema>;
export type Opportunity = z.infer<typeof opportunitySchema>;
export type ApplicationStage = z.infer<typeof applicationStageSchema>;
export type Application = z.infer<typeof applicationSchema>;
export type Relationship = z.infer<typeof relationshipSchema>;
export type Outreach = z.infer<typeof outreachSchema>;
export type OpportunityPage = z.infer<typeof opportunityPageSchema>;
export type ApplicationPage = z.infer<typeof applicationPageSchema>;
export type RelationshipPage = z.infer<typeof relationshipPageSchema>;
export type OutreachPage = z.infer<typeof outreachPageSchema>;
export type Operation = z.infer<typeof operationSchema>;
export type OperationLifecycleEvent = z.infer<
  typeof operationLifecycleEventSchema
>;
export type ApprovalEvidence = z.infer<typeof approvalEvidenceSchema>;
export type ExecutionReceiptPayload = z.infer<
  typeof executionReceiptPayloadSchema
>;
export type ExecutionReceiptEvidence = z.infer<
  typeof executionReceiptEvidenceSchema
>;
export type ContractHandle = z.infer<typeof contractHandleResponseSchema>;
