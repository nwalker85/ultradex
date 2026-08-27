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
  "applications.create",
  "applications.transition",
  "relationships.sync",
  "outreach.prepare",
  "outreach.approve",
  "outreach.send",
  "outreach.cancel",
  "evidence.export",
  "leads.create",
  "leads.convert",
  "organizations.create",
  "organizations.update",
  "workspace.initialize",
  "intent.set",
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

// CRM Governed Command Parameter Schemas
export const leadCreateParametersSchema = z
  .object({
    employer: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    sourceBoard: nonEmptyStringSchema.optional(),
    externalId: nonEmptyStringSchema.optional(),
    organizationId: nonEmptyStringSchema.optional(),
    location: nonEmptyStringSchema.optional(),
    remoteType: nonEmptyStringSchema.optional(),
    salaryMin: z.number().int().positive().optional(),
    salaryMax: z.number().int().positive().optional(),
    salaryCurrency: nonEmptyStringSchema.optional(),
    url: z.string().optional(),
    description: z.string().optional(),
    requirements: z.array(nonEmptyStringSchema).optional(),
    fitScore: z.number().min(0).max(100).optional(),
    matchBreakdown: z.record(z.string(), jsonValueSchema).optional(),
    riskFlags: z.array(nonEmptyStringSchema).optional(),
  })
  .strict();

export const leadConvertParametersSchema = z
  .object({
    leadId: nonEmptyStringSchema,
    stage: applicationStatusSchema.optional(),
    occurredAt: isoTimestampSchema.optional(),
    customTitle: nonEmptyStringSchema.optional(),
    targetRoleFamily: nonEmptyStringSchema.optional(),
    contactRefs: z.array(nonEmptyStringSchema).optional(),
    nextAction: nonEmptyStringSchema.optional(),
    nextActionDeadline: isoTimestampSchema.optional(),
  })
  .strict();

export const organizationCreateParametersSchema = z
  .object({
    name: nonEmptyStringSchema,
    domain: nonEmptyStringSchema.optional(),
    industry: nonEmptyStringSchema.optional(),
    size: nonEmptyStringSchema.optional(),
    advocacyRating: z.number().min(0).max(100).optional(),
    notes: z.string().optional(),
  })
  .strict();

export const organizationUpdateParametersSchema = z
  .object({
    organizationId: nonEmptyStringSchema,
    name: nonEmptyStringSchema.optional(),
    domain: nonEmptyStringSchema.optional(),
    industry: nonEmptyStringSchema.optional(),
    size: nonEmptyStringSchema.optional(),
    advocacyRating: z.number().min(0).max(100).optional(),
    notes: z.string().optional(),
  })
  .strict();

export const applicationCreateParametersSchema = z
  .object({
    opportunityId: nonEmptyStringSchema,
    stage: applicationStatusSchema.optional(),
    occurredAt: isoTimestampSchema.optional(),
    sourceEvidenceId: opaqueReferenceSchema("evidence").optional(),
  })
  .strict();

export const outreachCancelParametersSchema = z
  .object({
    outreachId: nonEmptyStringSchema,
    reason: nonEmptyStringSchema.optional(),
  })
  .strict();

export const workspaceInitializeParametersSchema = z
  .object({
    workspaceId: nonEmptyStringSchema.optional(),
  })
  .strict();

export const intentSetParametersSchema = z
  .object({
    targetRoleFamilies: z.array(nonEmptyStringSchema).optional(),
    targetDomains: z.array(nonEmptyStringSchema).optional(),
    seniorityBand: nonEmptyStringSchema.optional(),
    locationPreference: nonEmptyStringSchema.optional(),
    remotePreference: nonEmptyStringSchema.optional(),
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
      commandName: z.literal("applications.create"),
      parameters: applicationCreateParametersSchema,
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
      commandName: z.literal("outreach.cancel"),
      parameters: outreachCancelParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("evidence.export"),
      parameters: evidenceExportParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("leads.create"),
      parameters: leadCreateParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("leads.convert"),
      parameters: leadConvertParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("organizations.create"),
      parameters: organizationCreateParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("organizations.update"),
      parameters: organizationUpdateParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("workspace.initialize"),
      parameters: workspaceInitializeParametersSchema,
    })
    .strict(),
  z
    .object({
      commandName: z.literal("intent.set"),
      parameters: intentSetParametersSchema,
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
    organizationId: nonEmptyStringSchema.nullable().optional(),
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
    id: z.number().int().nonnegative(),
    operationId: nonEmptyStringSchema,
    eventType: nonEmptyStringSchema,
    timestamp: isoTimestampSchema,
    payload: jsonValueSchema.nullable(),
  })
  .strict();

export const approvalEvidenceSchema = z
  .object({
    approvalId: nonEmptyStringSchema,
    outreachId: nonEmptyStringSchema,
    messageCommitment: sha256DigestSchema,
    channel: outreachChannelSchema,
    approvedBy: nonEmptyStringSchema,
    issuedAt: isoTimestampSchema,
    expiresAt: isoTimestampSchema,
    status: z.literal("approved"),
  })
  .strict();

export const executionReceiptPayloadSchema = z
  .object({
    contract_version: z.literal("accountability.v1"),
    receipt_id: opaqueIdSchema,
    event_id: opaqueIdSchema,
    stream_pairwise_id: pairwiseIdSchema,
    sequence: z.number().int().positive(),
    subject_pairwise_id: pairwiseIdSchema,
    tenant_scope: z
      .object({
        scheme: z.literal("hmac_sha256_v1"),
        purpose: nonEmptyStringSchema,
        digest: sha256DigestSchema,
      })
      .strict(),
    purpose: nonEmptyStringSchema,
    request_id: opaqueIdSchema,
    idempotency_key: opaqueIdSchema,
    action_commitment: z
      .object({
        scheme: z.literal("hmac_sha256_v1"),
        purpose: nonEmptyStringSchema,
        digest: sha256DigestSchema,
      })
      .strict(),
    execution_id: opaqueIdSchema,
    executor_pairwise_id: pairwiseIdSchema,
    status: z.enum(["succeeded", "failed", "refused"]),
    started_at: isoTimestampSchema,
    completed_at: wholeMinuteTimestampSchema,
    result_commitment: z
      .object({
        scheme: z.literal("hmac_sha256_v1"),
        purpose: nonEmptyStringSchema,
        digest: sha256DigestSchema,
      })
      .strict(),
    reason_code: nonEmptyStringSchema.nullable(),
    daml_transaction: jsonValueSchema.nullable(),
    signature: z
      .object({
        algorithm: z.literal("ed25519"),
        key_id: pairwiseIdSchema,
        signature: nonEmptyStringSchema,
      })
      .strict(),
  })
  .strict();

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

// ===========================================================================
// Milestone M4: Candidate Profile & Taxonomy Schemas
// ===========================================================================

export const skillTierSchema = z.enum([
  "expert",
  "advanced",
  "intermediate",
  "familiar",
]);

export const skillCategorySchema = z.enum([
  "ai_ml",
  "distributed_systems",
  "cloud_infra",
  "backend_api",
  "frontend_fullstack",
  "security_governance",
  "leadership_strategy",
]);

export const skillItemSchema = z
  .object({
    name: nonEmptyStringSchema,
    category: skillCategorySchema,
    tier: skillTierSchema,
    yearsExperience: z.number().int().nonnegative(),
    keywords: z.array(nonEmptyStringSchema),
    description: z.string(),
    highlights: z.array(nonEmptyStringSchema),
  })
  .strict();

export const mlDepthSubdomainSchema = z
  .object({
    name: nonEmptyStringSchema,
    experienceLevel: nonEmptyStringSchema,
    years: z.number().int().nonnegative(),
    coreTechnologies: z.array(nonEmptyStringSchema),
    architecturalPatterns: z.array(nonEmptyStringSchema),
    productionMilestones: z.array(nonEmptyStringSchema),
  })
  .strict();

export const productionMLDepthSchema = z
  .object({
    llmOrchestration: mlDepthSubdomainSchema,
    asrTtsVoice: mlDepthSubdomainSchema,
    fineTuningAdaptation: mlDepthSubdomainSchema,
    embeddingsRag: mlDepthSubdomainSchema,
    agentLoopsTooling: mlDepthSubdomainSchema,
    inferenceHardware: mlDepthSubdomainSchema,
    llmSystems: z.array(nonEmptyStringSchema),
    agenticOrchestration: z.array(nonEmptyStringSchema),
    voiceSpeechAi: z.array(nonEmptyStringSchema),
    ragVectorSearch: z.array(nonEmptyStringSchema),
    fineTuningEvals: z.array(nonEmptyStringSchema),
    edgeQuantization: z.array(nonEmptyStringSchema),
  })
  .strict();

export const workExperienceItemSchema = z
  .object({
    company: nonEmptyStringSchema,
    role: nonEmptyStringSchema,
    startDate: nonEmptyStringSchema,
    endDate: nonEmptyStringSchema.nullable(),
    isCurrent: z.boolean(),
    location: nonEmptyStringSchema,
    remoteType: nonEmptyStringSchema,
    summary: z.string(),
    keyAchievements: z.array(nonEmptyStringSchema),
    technologies: z.array(nonEmptyStringSchema),
  })
  .strict();

export const educationItemSchema = z
  .object({
    institution: nonEmptyStringSchema,
    degree: nonEmptyStringSchema,
    fieldOfStudy: nonEmptyStringSchema,
    graduationYear: z.number().int().nullable(),
    notes: z.string().nullable(),
  })
  .strict();

export const projectHighlightSchema = z
  .object({
    name: nonEmptyStringSchema,
    role: nonEmptyStringSchema,
    description: z.string(),
    url: z.string().nullable(),
    technologies: z.array(nonEmptyStringSchema),
  })
  .strict();

export const targetRoleConfigSchema = z
  .object({
    targetRoles: z.array(nonEmptyStringSchema),
    targetRoleFamilies: z.array(nonEmptyStringSchema),
    targetDomains: z.array(nonEmptyStringSchema),
    seniorityBand: nonEmptyStringSchema,
    locationPreference: nonEmptyStringSchema,
    remotePreference: nonEmptyStringSchema,
  })
  .strict();

export const compensationExpectationsSchema = z
  .object({
    minBase: z.number().int().positive(),
    targetTotal: z.number().int().positive(),
    minTotal: z.number().int().positive(),
    baseMinimumUsd: z.number().int().positive().optional(),
    targetTotalCompUsd: z.number().int().positive().optional(),
    minimumTotalCompUsd: z.number().int().positive().optional(),
    equityPreference: nonEmptyStringSchema.optional(),
    currency: nonEmptyStringSchema,
    employmentType: nonEmptyStringSchema.optional(),
    locationPreference: nonEmptyStringSchema.optional(),
  })
  .strict();

export const candidateBioSchema = z
  .object({
    fullName: nonEmptyStringSchema,
    headline: nonEmptyStringSchema,
    summary: nonEmptyStringSchema,
    email: z.string().nullable(),
    phone: z.string().nullable(),
    location: nonEmptyStringSchema,
    linkedinUrl: z.string().nullable(),
    githubUrl: z.string().nullable(),
    portfolioUrl: z.string().nullable(),
  })
  .strict();

export const candidateProfileSchema = z
  .object({
    candidateName: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    resumeText: z.string().optional(),
    bio: candidateBioSchema,
    targetRoles: z.array(nonEmptyStringSchema),
    targetDomains: z.array(nonEmptyStringSchema),
    targetRoleFamilies: z.array(nonEmptyStringSchema).optional(),
    targetRoleConfig: targetRoleConfigSchema.optional(),
    compensation: compensationExpectationsSchema,
    skills: z.array(skillItemSchema),
    expertSkills: z.array(skillItemSchema).optional(),
    advancedSkills: z.array(skillItemSchema).optional(),
    productionMl: productionMLDepthSchema,
    experience: z.array(workExperienceItemSchema).optional(),
    education: z.array(educationItemSchema).optional(),
    projects: z.array(projectHighlightSchema).optional(),
    updatedAt: isoTimestampSchema,
  })
  .strict();

// ===========================================================================
// Milestone M4: Leads & Organizations Schemas
// ===========================================================================

export const leadStatusSchema = z.enum([
  "discovered",
  "unapplied",
  "converted",
  "dismissed",
]);

export const leadSchema = z
  .object({
    id: nonEmptyStringSchema,
    sourceBoard: nonEmptyStringSchema,
    externalId: nonEmptyStringSchema.nullable(),
    employer: nonEmptyStringSchema,
    organizationId: nonEmptyStringSchema.nullable(),
    title: nonEmptyStringSchema,
    location: nonEmptyStringSchema.nullable(),
    remoteType: nonEmptyStringSchema,
    salaryMin: z.number().int().nullable(),
    salaryMax: z.number().int().nullable(),
    salaryCurrency: nonEmptyStringSchema,
    url: z.string().nullable(),
    description: z.string().nullable(),
    requirements: z.array(nonEmptyStringSchema),
    fitScore: z.number().min(0).max(100).nullable(),
    matchBreakdown: z.record(z.string(), jsonValueSchema),
    riskFlags: z.array(nonEmptyStringSchema),
    state: leadStatusSchema,
    convertedOpportunityId: nonEmptyStringSchema.nullable(),
    freshness: projectionFreshnessSchema.nullable().optional(),
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const leadPageSchema = z
  .object({
    items: z.array(leadSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const organizationSchema = z
  .object({
    id: nonEmptyStringSchema,
    name: nonEmptyStringSchema,
    domain: nonEmptyStringSchema.nullable(),
    industry: nonEmptyStringSchema.nullable(),
    size: nonEmptyStringSchema.nullable(),
    advocacyRating: z.number().min(0).max(100).nullable(),
    notes: z.string().nullable(),
    freshness: projectionFreshnessSchema.nullable().optional(),
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const organizationPageSchema = z
  .object({
    items: z.array(organizationSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

// ===========================================================================
// Milestone M4: Contacts Schemas
// ===========================================================================

export const communicationEntrySchema = z
  .object({
    id: nonEmptyStringSchema,
    timestamp: isoTimestampSchema,
    channel: z.enum(["gmail", "linkedin", "dex"]),
    direction: z.enum(["inbound", "outbound"]),
    subject: nonEmptyStringSchema,
    summary: z.string(),
    messageId: nonEmptyStringSchema.nullable().optional(),
    evidenceRef: nonEmptyStringSchema.nullable().optional(),
    threadId: nonEmptyStringSchema.nullable().optional(),
  })
  .strict();

export const contactSchema = z
  .object({
    id: nonEmptyStringSchema,
    name: nonEmptyStringSchema,
    email: z.string().nullable(),
    company: nonEmptyStringSchema.nullable(),
    jobTitle: nonEmptyStringSchema.nullable(),
    phone: z.string().nullable(),
    notes: z.string().nullable(),
    lastContacted: isoTimestampSchema.nullable(),
    aiValue: z.number().min(0).max(100).nullable(),
    aiReason: z.string().nullable(),
    outreachStrategy: z.string().nullable(),
    suggestedTiming: z.string().nullable(),
    lastAnalyzed: isoTimestampSchema.nullable(),
    advocacyScore: z.number().min(0).max(100).nullable(),
    organizationId: nonEmptyStringSchema.nullable(),
    crmNotes: z.string().nullable(),
    communicationHistory: z.array(communicationEntrySchema),
    linkedinUrl: z.string().nullable(),
    relationshipTier: nonEmptyStringSchema.nullable(),
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const contactPageSchema = z
  .object({
    items: z.array(contactSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

// ===========================================================================
// Milestone M4: Copilot Next Best Actions & Recruiter Replies Schemas
// ===========================================================================

export const actionUrgencySchema = z.enum(["P0", "P1", "P2", "P3"]);

export const actionTypeSchema = z.enum([
  "reply_recruiter",
  "follow_up_application",
  "complete_application_task",
  "convert_high_fit_lead",
  "network_outreach",
  "send_thank_you",
  "schedule_interview",
]);

export const nextBestActionSchema = z
  .object({
    id: nonEmptyStringSchema,
    urgency: actionUrgencySchema,
    actionType: actionTypeSchema,
    title: nonEmptyStringSchema,
    description: z.string(),
    entityType: z.enum([
      "lead",
      "application",
      "opportunity",
      "contact",
      "message",
    ]),
    entityId: nonEmptyStringSchema,
    score: z.number().min(0).max(100),
    dueDate: isoTimestampSchema.nullable(),
    actionUrl: nonEmptyStringSchema,
    metadata: z.record(z.string(), jsonValueSchema),
    createdAt: isoTimestampSchema,
  })
  .strict();

export const recruiterPillTypeSchema = z.enum([
  "accept_and_schedule",
  "request_scope_and_comp",
  "polite_pass",
]);

export const recruiterPillReplySchema = z
  .object({
    pillType: recruiterPillTypeSchema,
    label: nonEmptyStringSchema,
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    bodyHtml: z.string().nullable(),
    calendarSlotsInjected: z.array(nonEmptyStringSchema),
    requiresApproval: z.boolean(),
    contextSummary: nonEmptyStringSchema,
  })
  .strict();

export const recruiterPillSetSchema = z
  .object({
    incomingMessageId: nonEmptyStringSchema,
    senderName: nonEmptyStringSchema,
    senderEmailOrHandle: nonEmptyStringSchema,
    roleMentioned: nonEmptyStringSchema.nullable(),
    companyMentioned: nonEmptyStringSchema.nullable(),
    pills: z.array(recruiterPillReplySchema),
    generatedAt: isoTimestampSchema,
  })
  .strict();

export const inboundMessageContextSchema = z
  .object({
    messageId: nonEmptyStringSchema.optional(),
    senderName: nonEmptyStringSchema,
    senderEmailOrHandle: nonEmptyStringSchema,
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    receivedAt: isoTimestampSchema.optional(),
    channel: z.enum(["gmail", "linkedin"]).optional(),
    companyMentioned: nonEmptyStringSchema.optional(),
    roleMentioned: nonEmptyStringSchema.optional(),
    salaryMentioned: nonEmptyStringSchema.optional(),
    techStackMentioned: z.array(nonEmptyStringSchema).optional(),
    calendarSlots: z.array(nonEmptyStringSchema).optional(),
  })
  .strict();

// ===========================================================================
// Milestone M4: Calendar & Availability Schemas
// ===========================================================================

export const calendarEventStatusSchema = z.enum([
  "confirmed",
  "tentative",
  "cancelled",
]);

export const calendarTransparencySchema = z.enum(["opaque", "transparent"]);

export const interviewRoundTypeSchema = z.enum([
  "recruiter_screen",
  "hiring_manager_screen",
  "technical_deep_dive",
  "system_design",
  "coding_architecture",
  "executive_culture",
  "onsite_loop",
  "offer_review",
  "unknown",
]);

export const calendarEventSchema = z
  .object({
    id: nonEmptyStringSchema,
    summary: nonEmptyStringSchema,
    description: z.string().nullable(),
    start: isoTimestampSchema,
    end: isoTimestampSchema,
    isAllDay: z.boolean(),
    status: calendarEventStatusSchema,
    transparency: calendarTransparencySchema,
    location: z.string().nullable(),
    meetingLink: z.string().nullable(),
    attendees: z.array(nonEmptyStringSchema),
    organizerEmail: z.string().nullable(),
    isBusy: z.boolean().optional(),
  })
  .strict();

export const timeSlotSchema = z
  .object({
    start: isoTimestampSchema,
    end: isoTimestampSchema,
    durationMinutes: z.number().int().positive(),
    dayKey: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    formattedCt: nonEmptyStringSchema,
  })
  .strict();

export const dailyAvailabilitySchema = z
  .object({
    dateStr: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    dayName: nonEmptyStringSchema,
    slots30min: z.array(timeSlotSchema),
    slots45min: z.array(timeSlotSchema),
  })
  .strict();

// ===========================================================================
// Milestone M4: Omnichannel Messaging Schemas
// ===========================================================================

export const messageChannelSchema = z.enum(["gmail", "linkedin", "dex"]);
export const messageDirectionSchema = z.enum(["inbound", "outbound"]);
export const messageStatusSchema = z.enum([
  "draft",
  "pending_approval",
  "approved",
  "queued",
  "sending",
  "sent",
  "failed",
  "cancelled",
]);

export const composeMessageInputSchema = z
  .object({
    recipientAddress: nonEmptyStringSchema,
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    bodyHtml: z.string().optional(),
    channel: messageChannelSchema.optional(),
    recipientName: nonEmptyStringSchema.optional(),
    recipientId: nonEmptyStringSchema.optional(),
    threadId: nonEmptyStringSchema.optional(),
    inReplyTo: nonEmptyStringSchema.optional(),
    references: nonEmptyStringSchema.optional(),
    opportunityId: nonEmptyStringSchema.optional(),
    relationshipId: nonEmptyStringSchema.optional(),
  })
  .strict();

export const outboxMessageSchema = z
  .object({
    id: nonEmptyStringSchema,
    channel: messageChannelSchema,
    direction: messageDirectionSchema,
    recipientAddress: nonEmptyStringSchema,
    recipientName: nonEmptyStringSchema.nullable(),
    recipientId: nonEmptyStringSchema.nullable(),
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    bodyHtml: z.string().nullable(),
    threadId: nonEmptyStringSchema.nullable(),
    inReplyTo: nonEmptyStringSchema.nullable(),
    references: nonEmptyStringSchema.nullable(),
    status: messageStatusSchema,
    messageCommitment: sha256DigestSchema.or(z.literal("")),
    approvalId: nonEmptyStringSchema.nullable(),
    sentEvidenceRef: nonEmptyStringSchema.nullable(),
    externalMessageId: nonEmptyStringSchema.nullable(),
    errorMessage: z.string().nullable(),
    createdAt: isoTimestampSchema,
    sentAt: isoTimestampSchema.nullable(),
  })
  .strict();

export const messagePageSchema = z
  .object({
    items: z.array(outboxMessageSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const sendResultSchema = z
  .object({
    success: z.boolean(),
    messageId: nonEmptyStringSchema,
    channel: messageChannelSchema,
    externalId: nonEmptyStringSchema.nullable(),
    threadId: nonEmptyStringSchema.nullable(),
    evidenceRef: nonEmptyStringSchema.nullable(),
    error: z.string().nullable(),
    sentAt: isoTimestampSchema,
  })
  .strict();

// ===========================================================================
// Milestone M4: Sovereign Voice & Interview Debrief Schemas
// ===========================================================================

export const speakerRoleSchema = z.enum([
  "candidate",
  "interviewer",
  "recruiter",
  "unknown",
]);

export const transcriptSegmentSchema = z
  .object({
    offsetMs: z.number().int().nonnegative(),
    speaker: nonEmptyStringSchema,
    role: speakerRoleSchema,
    text: nonEmptyStringSchema,
    confidence: z.number().min(0).max(1),
  })
  .strict();

export const interviewMetadataSchema = z
  .object({
    company: nonEmptyStringSchema,
    role: nonEmptyStringSchema,
    roundType: nonEmptyStringSchema,
    interviewDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    interviewerNames: z.array(nonEmptyStringSchema),
    interviewerTitles: z.array(nonEmptyStringSchema),
    durationMinutes: z.number().int().positive(),
    audioRef: nonEmptyStringSchema.nullable(),
    opportunityId: nonEmptyStringSchema.nullable(),
    contactIds: z.array(nonEmptyStringSchema),
  })
  .strict();

export const questionAnswerPairSchema = z
  .object({
    id: nonEmptyStringSchema,
    question: nonEmptyStringSchema,
    askedBy: nonEmptyStringSchema,
    category: nonEmptyStringSchema,
    answerSummary: nonEmptyStringSchema,
    keyPointsMentioned: z.array(nonEmptyStringSchema),
    effectivenessScore: z.number().min(0).max(10),
    followUpNeeded: z.boolean(),
  })
  .strict();

export const fitAssessmentSchema = z
  .object({
    overallScore: z.number().min(0).max(100),
    technicalAlignment: nonEmptyStringSchema,
    leadershipAlignment: nonEmptyStringSchema,
    compensationAlignment: nonEmptyStringSchema,
    greenFlags: z.array(nonEmptyStringSchema),
    redFlags: z.array(nonEmptyStringSchema),
    cultureNotes: z.string(),
    recommendation: nonEmptyStringSchema,
  })
  .strict();

export const interviewActionItemSchema = z
  .object({
    id: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    actionType: nonEmptyStringSchema,
    priority: z.enum(["p0", "p1", "p2", "P0", "P1", "P2"]),
    dueDate: nonEmptyStringSchema,
    recipientName: nonEmptyStringSchema.nullable(),
    recipientEmail: z.string().nullable(),
    draftContent: z.string().nullable(),
    opportunityId: nonEmptyStringSchema.nullable(),
    isCompleted: z.boolean(),
  })
  .strict();

export const interviewDebriefSchema = z
  .object({
    id: nonEmptyStringSchema,
    createdAt: isoTimestampSchema,
    metadata: interviewMetadataSchema,
    executiveSummary: nonEmptyStringSchema,
    questionsAndAnswers: z.array(questionAnswerPairSchema),
    fitAssessment: fitAssessmentSchema,
    actionItems: z.array(interviewActionItemSchema),
    rawTranscript: z.string(),
    transcriptSegments: z.array(transcriptSegmentSchema),
  })
  .strict();

export const interviewDebriefPageSchema = z
  .object({
    items: z.array(interviewDebriefSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

// ===========================================================================
// Contract Handle Response
// ===========================================================================

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

const contractHandleWireShape = {
  contract_id: nonEmptyStringSchema,
  operation_id: nonEmptyStringSchema,
  submitted_at: isoTimestampSchema,
  correlation_id: nonEmptyStringSchema.optional(),
  expires_at: isoTimestampSchema.nullable().optional(),
  status_url: nonEmptyStringSchema.nullable().optional(),
  events_url: nonEmptyStringSchema.nullable().optional(),
};

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

// Inferred TypeScript types
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
export type ApplicationCreateParameters = z.infer<
  typeof applicationCreateParametersSchema
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
export type OutreachCancelParameters = z.infer<
  typeof outreachCancelParametersSchema
>;
export type EvidenceExportParameters = z.infer<
  typeof evidenceExportParametersSchema
>;
export type LeadCreateParameters = z.infer<
  typeof leadCreateParametersSchema
>;
export type LeadConvertParameters = z.infer<
  typeof leadConvertParametersSchema
>;
export type OrganizationCreateParameters = z.infer<
  typeof organizationCreateParametersSchema
>;
export type OrganizationUpdateParameters = z.infer<
  typeof organizationUpdateParametersSchema
>;
export type WorkspaceInitializeParameters = z.infer<
  typeof workspaceInitializeParametersSchema
>;
export type IntentSetParameters = z.infer<
  typeof intentSetParametersSchema
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

// Milestone M4 Types
export type SkillTier = z.infer<typeof skillTierSchema>;
export type SkillCategory = z.infer<typeof skillCategorySchema>;
export type SkillItem = z.infer<typeof skillItemSchema>;
export type MLDepthSubdomain = z.infer<typeof mlDepthSubdomainSchema>;
export type ProductionMLDepth = z.infer<typeof productionMLDepthSchema>;
export type WorkExperienceItem = z.infer<typeof workExperienceItemSchema>;
export type EducationItem = z.infer<typeof educationItemSchema>;
export type ProjectHighlight = z.infer<typeof projectHighlightSchema>;
export type TargetRoleConfig = z.infer<typeof targetRoleConfigSchema>;
export type CompensationExpectations = z.infer<typeof compensationExpectationsSchema>;
export type CandidateBio = z.infer<typeof candidateBioSchema>;
export type CandidateProfile = z.infer<typeof candidateProfileSchema>;
export type LeadStatus = z.infer<typeof leadStatusSchema>;
export type Lead = z.infer<typeof leadSchema>;
export type LeadPage = z.infer<typeof leadPageSchema>;
export type Organization = z.infer<typeof organizationSchema>;
export type OrganizationPage = z.infer<typeof organizationPageSchema>;
export type CommunicationEntry = z.infer<typeof communicationEntrySchema>;
export type Contact = z.infer<typeof contactSchema>;
export type ContactPage = z.infer<typeof contactPageSchema>;
export type ActionUrgency = z.infer<typeof actionUrgencySchema>;
export type ActionType = z.infer<typeof actionTypeSchema>;
export type NextBestAction = z.infer<typeof nextBestActionSchema>;
export type RecruiterPillType = z.infer<typeof recruiterPillTypeSchema>;
export type RecruiterPillReply = z.infer<typeof recruiterPillReplySchema>;
export type RecruiterPillSet = z.infer<typeof recruiterPillSetSchema>;
export type InboundMessageContext = z.infer<typeof inboundMessageContextSchema>;
export type CalendarEventStatus = z.infer<typeof calendarEventStatusSchema>;
export type CalendarTransparency = z.infer<typeof calendarTransparencySchema>;
export type InterviewRoundType = z.infer<typeof interviewRoundTypeSchema>;
export type CalendarEvent = z.infer<typeof calendarEventSchema>;
export type TimeSlot = z.infer<typeof timeSlotSchema>;
export type DailyAvailability = z.infer<typeof dailyAvailabilitySchema>;
export type MessageChannel = z.infer<typeof messageChannelSchema>;
export type MessageDirection = z.infer<typeof messageDirectionSchema>;
export type MessageStatus = z.infer<typeof messageStatusSchema>;
export type ComposeMessageInput = z.infer<typeof composeMessageInputSchema>;
export type OutboxMessage = z.infer<typeof outboxMessageSchema>;
export type MessagePage = z.infer<typeof messagePageSchema>;
export type SendResult = z.infer<typeof sendResultSchema>;
export type SpeakerRole = z.infer<typeof speakerRoleSchema>;
export type TranscriptSegment = z.infer<typeof transcriptSegmentSchema>;
export type InterviewMetadata = z.infer<typeof interviewMetadataSchema>;
export type QuestionAnswerPair = z.infer<typeof questionAnswerPairSchema>;
export type FitAssessment = z.infer<typeof fitAssessmentSchema>;
export type InterviewActionItem = z.infer<typeof interviewActionItemSchema>;
export type InterviewDebrief = z.infer<typeof interviewDebriefSchema>;
export type InterviewDebriefPage = z.infer<typeof interviewDebriefPageSchema>;
