import { z } from "zod";

import {
  applicationPageSchema,
  applicationStatusSchema,
  approvalEvidenceSchema,
  executionReceiptEvidenceSchema,
  operationLifecycleEventSchema,
  operationSchema,
  operationStatusSchema,
  opportunityPageSchema,
  opportunityStatusSchema,
  outreachPageSchema,
  outreachStatusSchema,
  relationshipPageSchema,
} from "./contracts.js";

export interface OpportunityListInput {
  readonly first?: number;
  readonly after?: string;
  readonly status?: z.infer<typeof opportunityStatusSchema>;
}

export interface ApplicationListInput {
  readonly first?: number;
  readonly after?: string;
  readonly status?: z.infer<typeof applicationStatusSchema>;
  readonly opportunityId?: string;
}

export interface RelationshipListInput {
  readonly first?: number;
  readonly after?: string;
  readonly opportunityId?: string;
}

export interface OutreachListInput {
  readonly first?: number;
  readonly after?: string;
  readonly status?: z.infer<typeof outreachStatusSchema>;
  readonly opportunityId?: string;
}

export interface OperationListInput {
  readonly limit?: number;
  readonly status?: z.infer<typeof operationStatusSchema>;
}

export interface EventPageInput {
  readonly first?: number;
  readonly after?: number;
}

const firstSchema = z.number().int().min(1).max(100);
const cursorSchema = z.string().min(1);

const opportunityListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    status: opportunityStatusSchema.optional(),
  })
  .strict();

const applicationListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    status: applicationStatusSchema.optional(),
    opportunityId: cursorSchema.optional(),
  })
  .strict();

const relationshipListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    opportunityId: cursorSchema.optional(),
  })
  .strict();

const outreachListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    status: outreachStatusSchema.optional(),
    opportunityId: cursorSchema.optional(),
  })
  .strict();

const operationListInputSchema = z
  .object({
    limit: firstSchema.optional(),
    status: operationStatusSchema.optional(),
  })
  .strict();

const eventPageInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: z.number().int().positive().optional(),
  })
  .strict();

function optionalVariables(
  values: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined),
  );
}

export function opportunityVariables(
  input: OpportunityListInput = {},
): Record<string, unknown> {
  const value = opportunityListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    status: value.status,
  });
}

export function applicationVariables(
  input: ApplicationListInput = {},
): Record<string, unknown> {
  const value = applicationListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    status: value.status,
    opportunityId: value.opportunityId,
  });
}

export function relationshipVariables(
  input: RelationshipListInput = {},
): Record<string, unknown> {
  const value = relationshipListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    opportunityId: value.opportunityId,
  });
}

export function outreachVariables(
  input: OutreachListInput = {},
): Record<string, unknown> {
  const value = outreachListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    status: value.status,
    opportunityId: value.opportunityId,
  });
}

export function operationVariables(
  input: OperationListInput = {},
): Record<string, unknown> {
  const value = operationListInputSchema.parse(input);
  return optionalVariables({
    limit: value.limit ?? 10,
    status: value.status,
  });
}

export function eventVariables(
  operationId: string,
  input: EventPageInput = {},
): Record<string, unknown> {
  const id = cursorSchema.parse(operationId);
  const value = eventPageInputSchema.parse(input);
  return optionalVariables({
    operationId: id,
    first: value.first ?? 50,
    after: value.after,
  });
}

export function exactIdVariables(
  key: "id" | "operationId",
  value: string,
): Record<string, unknown> {
  return { [key]: cursorSchema.parse(value) };
}

export const LIST_OPPORTUNITIES_QUERY =
  "query ListOpportunities($first: Int!, $after: String, $status: String) { opportunities(first: $first, after: $after, status: $status) { items { opportunityId employer title location roleFamily status fitScore fitExplanation riskFlags evidenceRefs { evidenceId sourceKind sourceRef classification observedAt commitment redactedSummary } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const LIST_APPLICATIONS_QUERY =
  "query ListApplications($first: Int!, $after: String, $status: String, $opportunityId: String) { applications(first: $first, after: $after, status: $status, opportunityId: $opportunityId) { items { applicationId opportunityId status stageHistory { status occurredAt evidenceRef } artifactRefs nextAction nextActionAt freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const LIST_RELATIONSHIPS_QUERY =
  "query ListRelationships($first: Int!, $after: String, $opportunityId: String) { relationships(first: $first, after: $after, opportunityId: $opportunityId) { items { relationshipId opportunityId dexContactRef relevanceScore relevanceSummary freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const LIST_OUTREACH_QUERY =
  "query ListOutreach($first: Int!, $after: String, $status: String, $opportunityId: String) { outreach(first: $first, after: $after, status: $status, opportunityId: $opportunityId) { items { outreachId opportunityId relationshipId status channel messageCommitment approvalContractId sentEvidenceRef freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const LIST_OPERATIONS_QUERY =
  "query ListOperations($limit: Int!, $status: String) { operations(limit: $limit, status: $status) { id correlationId command status createdAt startedAt completedAt result error freshness { sourceEventId sourceEventPosition projectedAt lagMs status } } }";

export const GET_OPERATION_QUERY =
  "query GetOperation($id: String!) { operation(id: $id) { id correlationId command status createdAt startedAt completedAt result error freshness { sourceEventId sourceEventPosition projectedAt lagMs status } } }";

export const GET_OPERATION_EVENTS_QUERY =
  "query GetOperationEvents($operationId: String!, $first: Int!, $after: Int) { events(operationId: $operationId, first: $first, after: $after) { id operationId eventType timestamp payload } }";

export const GET_APPROVAL_QUERY =
  "query GetApproval($id: String!) { approval(id: $id) { approvalId outreachId messageCommitment channel approvedBy issuedAt expiresAt status } }";

export const GET_EXECUTION_RECEIPT_QUERY =
  "query GetExecutionReceipt($operationId: String!) { executionReceipt(operationId: $operationId) { receiptId operationId eventId status reasonCode payload receiptHash createdAt completedAt proofStatus } }";

export const opportunitiesResultSchema = z
  .object({ opportunities: opportunityPageSchema })
  .strict();
export const applicationsResultSchema = z
  .object({ applications: applicationPageSchema })
  .strict();
export const relationshipsResultSchema = z
  .object({ relationships: relationshipPageSchema })
  .strict();
export const outreachResultSchema = z
  .object({ outreach: outreachPageSchema })
  .strict();
export const operationsResultSchema = z
  .object({ operations: z.array(operationSchema) })
  .strict();
export const operationResultSchema = z
  .object({ operation: operationSchema.nullable() })
  .strict();
export const eventsResultSchema = z
  .object({ events: z.array(operationLifecycleEventSchema) })
  .strict();
export const approvalResultSchema = z
  .object({ approval: approvalEvidenceSchema.nullable() })
  .strict();
export const executionReceiptResultSchema = z
  .object({ executionReceipt: executionReceiptEvidenceSchema.nullable() })
  .strict();
