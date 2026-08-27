import { describe, expect, expectTypeOf, it } from "vitest";

import {
  UltradexClient,
  UltradexSchemaError,
  type ApplicationPage,
  type ApprovalEvidence,
  type ExecutionReceiptEvidence,
  type OpportunityPage,
  type Operation,
  type OperationLifecycleEvent,
  type OutreachPage,
  type RelationshipPage,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "../src/index.js";
import {
  syntheticApplicationPage,
  syntheticApprovalEvidence,
  syntheticCompletedOperation,
  syntheticExecutionReceiptEvidence,
  syntheticLifecycleEvent,
  syntheticOpportunityPage,
  syntheticOutreachPage,
  syntheticRelationshipPage,
} from "./fixtures.js";

const EXPECTED_OPPORTUNITIES_QUERY =
  "query ListOpportunities($first: Int!, $after: String, $status: String, $organizationId: String) { opportunities(first: $first, after: $after, status: $status, organizationId: $organizationId) { items { opportunityId organizationId employer title location roleFamily status fitScore fitExplanation riskFlags evidenceRefs { evidenceId sourceKind sourceRef classification observedAt commitment redactedSummary } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";
const EXPECTED_APPLICATIONS_QUERY =
  "query ListApplications($first: Int!, $after: String, $status: String, $opportunityId: String) { applications(first: $first, after: $after, status: $status, opportunityId: $opportunityId) { items { applicationId opportunityId status stageHistory { status occurredAt evidenceRef } artifactRefs nextAction nextActionAt freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";
const EXPECTED_RELATIONSHIPS_QUERY =
  "query ListRelationships($first: Int!, $after: String, $opportunityId: String) { relationships(first: $first, after: $after, opportunityId: $opportunityId) { items { relationshipId opportunityId dexContactRef relevanceScore relevanceSummary freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";
const EXPECTED_OUTREACH_QUERY =
  "query ListOutreach($first: Int!, $after: String, $status: String, $opportunityId: String) { outreach(first: $first, after: $after, status: $status, opportunityId: $opportunityId) { items { outreachId opportunityId relationshipId status channel messageCommitment approvalContractId sentEvidenceRef freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";
const EXPECTED_OPERATIONS_QUERY =
  "query ListOperations($limit: Int!, $status: String) { operations(limit: $limit, status: $status) { id correlationId command status createdAt startedAt completedAt result error freshness { sourceEventId sourceEventPosition projectedAt lagMs status } } }";
const EXPECTED_OPERATION_QUERY =
  "query GetOperation($id: String!) { operation(id: $id) { id correlationId command status createdAt startedAt completedAt result error freshness { sourceEventId sourceEventPosition projectedAt lagMs status } } }";
const EXPECTED_EVENTS_QUERY =
  "query GetOperationEvents($operationId: String!, $first: Int!, $after: Int) { events(operationId: $operationId, first: $first, after: $after) { id operationId eventType timestamp payload } }";
const EXPECTED_APPROVAL_QUERY =
  "query GetApproval($id: String!) { approval(id: $id) { approvalId outreachId messageCommitment channel approvedBy issuedAt expiresAt status } }";
const EXPECTED_RECEIPT_QUERY =
  "query GetExecutionReceipt($operationId: String!) { executionReceipt(operationId: $operationId) { receiptId operationId eventId status reasonCode payload receiptHash createdAt completedAt proofStatus } }";

class RecordingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  constructor(private readonly responses: readonly unknown[]) {}

  async request(request: UltradexRequest): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    const value = this.responses[this.requests.length - 1];
    if (value === undefined) {
      throw new Error("Synthetic transport queue exhausted");
    }
    return {
      status: 200,
      body: JSON.stringify(value),
    };
  }
}

function createClient(transport: UltradexTransport): UltradexClient {
  return new UltradexClient({
    baseUrl: "https://ultradex.synthetic.example",
    token: "synthetic-token",
    transport,
  });
}

function graphqlData(field: string, value: unknown): unknown {
  return {
    data: {
      [field]: value,
    },
  };
}

function requestBody(request: UltradexRequest): unknown {
  if (request.body === undefined) {
    throw new Error("Expected a GraphQL request body");
  }
  return JSON.parse(request.body) as unknown;
}

describe("projection read contracts", () => {
  it("uses typed SDK-owned documents for every projection page", async () => {
    const transport = new RecordingTransport([
      graphqlData("opportunities", syntheticOpportunityPage),
      graphqlData("applications", syntheticApplicationPage),
      graphqlData("relationships", syntheticRelationshipPage),
      graphqlData("outreach", syntheticOutreachPage),
    ]);
    const client = createClient(transport);

    const opportunities = await client.listOpportunities({
      first: 2,
      after: "opportunity-cursor-001",
      status: "qualified",
    });
    const applications = await client.listApplications({
      first: 3,
      after: "application-cursor-001",
      status: "applied",
      opportunityId: "opportunity-synthetic-001",
    });
    const relationships = await client.listRelationships({
      first: 4,
      after: "relationship-cursor-001",
      opportunityId: "opportunity-synthetic-001",
    });
    const outreach = await client.listOutreach({
      first: 5,
      after: "outreach-cursor-001",
      status: "approved",
      opportunityId: "opportunity-synthetic-001",
    });

    expect(opportunities).toEqual(syntheticOpportunityPage);
    expect(applications).toEqual(syntheticApplicationPage);
    expect(relationships).toEqual(syntheticRelationshipPage);
    expect(outreach).toEqual(syntheticOutreachPage);
    expectTypeOf(opportunities).toEqualTypeOf<OpportunityPage>();
    expectTypeOf(applications).toEqualTypeOf<ApplicationPage>();
    expectTypeOf(relationships).toEqualTypeOf<RelationshipPage>();
    expectTypeOf(outreach).toEqualTypeOf<OutreachPage>();
    expect(transport.requests[0]).toMatchObject({
      method: "POST",
      url: "https://ultradex.synthetic.example/api/graphql",
      headers: {
        Accept: "application/json",
        Authorization: "Bearer synthetic-token",
        "Content-Type": "application/json",
      },
      timeoutMs: 10_000,
    });
    expect(requestBody(transport.requests[0]!)).toEqual({
      query: EXPECTED_OPPORTUNITIES_QUERY,
      variables: {
        first: 2,
        after: "opportunity-cursor-001",
        status: "qualified",
      },
    });
    expect(requestBody(transport.requests[1]!)).toEqual({
      query: EXPECTED_APPLICATIONS_QUERY,
      variables: {
        first: 3,
        after: "application-cursor-001",
        status: "applied",
        opportunityId: "opportunity-synthetic-001",
      },
    });
    expect(requestBody(transport.requests[2]!)).toEqual({
      query: EXPECTED_RELATIONSHIPS_QUERY,
      variables: {
        first: 4,
        after: "relationship-cursor-001",
        opportunityId: "opportunity-synthetic-001",
      },
    });
    expect(requestBody(transport.requests[3]!)).toEqual({
      query: EXPECTED_OUTREACH_QUERY,
      variables: {
        first: 5,
        after: "outreach-cursor-001",
        status: "approved",
        opportunityId: "opportunity-synthetic-001",
      },
    });
  });

  it("preserves page freshness and cursors exactly", async () => {
    const transport = new RecordingTransport([
      graphqlData("opportunities", syntheticOpportunityPage),
    ]);

    const page = await createClient(transport).listOpportunities();

    expect(page.freshness).toEqual({
      sourceEventId: "event-checkpoint-opportunities",
      sourceEventPosition: "SYNTHETIC:2",
      projectedAt: "2026-07-29T12:00:03+00:00",
      lagMs: 13,
      status: "stale",
    });
    expect(page.nextCursor).toBe("opportunity-synthetic-001");
    expect(requestBody(transport.requests[0]!)).toEqual({
      query: EXPECTED_OPPORTUNITIES_QUERY,
      variables: {
        first: 25,
      },
    });
  });

  it("rejects incomplete pages before returning public data", async () => {
    const { nextCursor: _nextCursor, ...incompletePage } =
      syntheticOpportunityPage;
    const transport = new RecordingTransport([
      graphqlData("opportunities", incompletePage),
    ]);

    const pending = createClient(transport).listOpportunities();

    await expect(pending).rejects.toBeInstanceOf(UltradexSchemaError);
  });
});

describe("operation and lifecycle reads", () => {
  it("reads filtered operations, exact operations, and bounded events", async () => {
    const transport = new RecordingTransport([
      graphqlData("operations", [syntheticCompletedOperation]),
      graphqlData("operation", syntheticCompletedOperation),
      graphqlData("events", [syntheticLifecycleEvent]),
    ]);
    const client = createClient(transport);

    const operations = await client.listOperations({
      limit: 7,
      status: "completed",
    });
    const operation = await client.getOperation(
      "operation-synthetic-completed-001",
    );
    const events = await client.getOperationEvents(
      "operation-synthetic-completed-001",
      {
        first: 20,
        after: 100,
      },
    );

    expect(operations).toEqual([syntheticCompletedOperation]);
    expect(operation).toEqual(syntheticCompletedOperation);
    expect(events).toEqual([syntheticLifecycleEvent]);
    expectTypeOf(operations).toEqualTypeOf<Operation[]>();
    expectTypeOf(operation).toEqualTypeOf<Operation | null>();
    expectTypeOf(events).toEqualTypeOf<OperationLifecycleEvent[]>();
    expect(requestBody(transport.requests[0]!)).toEqual({
      query: EXPECTED_OPERATIONS_QUERY,
      variables: {
        limit: 7,
        status: "completed",
      },
    });
    expect(requestBody(transport.requests[1]!)).toEqual({
      query: EXPECTED_OPERATION_QUERY,
      variables: {
        id: "operation-synthetic-completed-001",
      },
    });
    expect(requestBody(transport.requests[2]!)).toEqual({
      query: EXPECTED_EVENTS_QUERY,
      variables: {
        operationId: "operation-synthetic-completed-001",
        first: 20,
        after: 100,
      },
    });
  });

  it("rejects a terminal operation without a completion timestamp", async () => {
    const transport = new RecordingTransport([
      graphqlData("operation", {
        ...syntheticCompletedOperation,
        completedAt: null,
      }),
    ]);

    const pending = createClient(transport).getOperation(
      "operation-synthetic-completed-001",
    );

    await expect(pending).rejects.toBeInstanceOf(UltradexSchemaError);
  });
});

describe("governed evidence reads", () => {
  it("resolves an exact approval with its complete binding", async () => {
    const transport = new RecordingTransport([
      graphqlData("approval", syntheticApprovalEvidence),
    ]);

    const approval = await createClient(transport).getApproval(
      "approval-synthetic-001",
    );

    expect(approval).toEqual(syntheticApprovalEvidence);
    expectTypeOf(approval).toEqualTypeOf<ApprovalEvidence | null>();
    expect(requestBody(transport.requests[0]!)).toEqual({
      query: EXPECTED_APPROVAL_QUERY,
      variables: {
        id: "approval-synthetic-001",
      },
    });
  });

  it("returns a server-recorded receipt without claiming signature verification", async () => {
    const transport = new RecordingTransport([
      graphqlData("executionReceipt", syntheticExecutionReceiptEvidence),
    ]);

    const receipt = await createClient(transport).getExecutionReceipt(
      "operation-synthetic-completed-001",
    );

    expect(receipt).toEqual(syntheticExecutionReceiptEvidence);
    expect(receipt?.proofStatus).toBe("server-recorded");
    expectTypeOf(receipt).toEqualTypeOf<ExecutionReceiptEvidence | null>();
    expect(requestBody(transport.requests[0]!)).toEqual({
      query: EXPECTED_RECEIPT_QUERY,
      variables: {
        operationId: "operation-synthetic-completed-001",
      },
    });
  });

  it("binds the outer completion timestamp to the signed payload instant", async () => {
    const transport = new RecordingTransport([
      graphqlData("executionReceipt", {
        ...syntheticExecutionReceiptEvidence,
        completedAt: "2026-07-29T07:01:00-05:00",
      }),
      graphqlData("executionReceipt", {
        ...syntheticExecutionReceiptEvidence,
        completedAt: "2026-07-29T12:02:00+00:00",
      }),
    ]);
    const client = createClient(transport);

    await expect(
      client.getExecutionReceipt("operation-synthetic-completed-001"),
    ).resolves.toMatchObject({
      completedAt: "2026-07-29T07:01:00-05:00",
    });
    await expect(
      client.getExecutionReceipt("operation-synthetic-completed-001"),
    ).rejects.toBeInstanceOf(UltradexSchemaError);
  });

  it("rejects incomplete approval and malformed receipt evidence", async () => {
    const {
      messageCommitment: _messageCommitment,
      ...incompleteApproval
    } = syntheticApprovalEvidence;
    const transport = new RecordingTransport([
      graphqlData("approval", incompleteApproval),
      graphqlData("executionReceipt", {
        ...syntheticExecutionReceiptEvidence,
        proofStatus: "signature-verified",
      }),
    ]);
    const client = createClient(transport);

    await expect(
      client.getApproval("approval-synthetic-001"),
    ).rejects.toBeInstanceOf(UltradexSchemaError);
    await expect(
      client.getExecutionReceipt("operation-synthetic-completed-001"),
    ).rejects.toBeInstanceOf(UltradexSchemaError);
  });
});

describe("Milestone M4 domain projection reads", () => {
  it("reads candidate profile and production ML depth", async () => {
    const { syntheticCandidateProfile } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("profile", syntheticCandidateProfile),
    ]);
    const client = createClient(transport);

    const profile = await client.getProfile();
    expect(profile.candidateName).toBe("Nate Walker");
    expect(profile.compensation.minBase).toBe(180000);
    expect(profile.productionMl.llmOrchestration.name).toBe("LLM Orchestration & Systems");
  });

  it("reads leads list and individual lead", async () => {
    const { syntheticLeadPage } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("leads", syntheticLeadPage),
      graphqlData("lead", syntheticLeadPage.items[0]),
    ]);
    const client = createClient(transport);

    const leads = await client.getLeads({ minFitScore: 80 });
    expect(leads.items).toHaveLength(1);
    expect(leads.items[0]?.employer).toBe("Anthropic");

    const lead = await client.getLead("lead-synthetic-001");
    expect(lead?.title).toBe("Principal AI Architect");
  });

  it("reads organizations list and individual organization", async () => {
    const { syntheticOrganizationPage } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("organizations", syntheticOrganizationPage),
      graphqlData("organization", syntheticOrganizationPage.items[0]),
    ]);
    const client = createClient(transport);

    const orgs = await client.getOrganizations({ sortBy: "name" });
    expect(orgs.items).toHaveLength(1);
    expect(orgs.items[0]?.name).toBe("Anthropic");

    const org = await client.getOrganization("org-synthetic-anthropic");
    expect(org?.advocacyRating).toBe(95);
  });

  it("reads contacts list and individual contact with communication history", async () => {
    const { syntheticContactPage } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("contacts", syntheticContactPage),
      graphqlData("contact", syntheticContactPage.items[0]),
    ]);
    const client = createClient(transport);

    const contacts = await client.getContacts({ search: "Alice" });
    expect(contacts.items).toHaveLength(1);
    expect(contacts.items[0]?.communicationHistory).toHaveLength(1);

    const contact = await client.getContact("contact-synthetic-001");
    expect(contact?.name).toBe("Alice Recruiter");
  });

  it("reads copilot next best actions", async () => {
    const { syntheticNextBestActions } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("nextBestActions", syntheticNextBestActions),
    ]);
    const client = createClient(transport);

    const actions = await client.getNextBestActions(5);
    expect(actions).toHaveLength(1);
    expect(actions[0]?.urgency).toBe("P0");
    expect(actions[0]?.actionType).toBe("reply_recruiter");
  });

  it("generates recruiter 3-pill replies", async () => {
    const { syntheticRecruiterPillSet } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("generateRecruiterReplies", syntheticRecruiterPillSet),
    ]);
    const client = createClient(transport);

    const replies = await client.generateRecruiterReplies({
      senderName: "Alice Recruiter",
      senderEmailOrHandle: "alice@anthropic.com",
      subject: "Principal Architect Role",
      bodyText: "Are you interested in chatting?",
    });
    expect(replies.senderName).toBe("Alice Recruiter");
    expect(replies.pills).toHaveLength(1);
    expect(replies.pills[0]?.pillType).toBe("accept_and_schedule");
  });

  it("computes availability slots and reads calendar events", async () => {
    const { syntheticDailyAvailability, syntheticCalendarEvents } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("availability", syntheticDailyAvailability),
      graphqlData("calendarEvents", syntheticCalendarEvents),
    ]);
    const client = createClient(transport);

    const avail = await client.getAvailability({
      startDate: "2026-08-25",
      endDate: "2026-08-27",
    });
    expect(avail).toHaveLength(1);
    expect(avail[0]?.slots30min[0]?.formattedCt).toContain("CT");

    const events = await client.getCalendarEvents();
    expect(events).toHaveLength(1);
    expect(events[0]?.summary).toBe("1:1 Architecture Sync");
  });

  it("reads messages page", async () => {
    const { syntheticMessagePage } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("messages", syntheticMessagePage),
    ]);
    const client = createClient(transport);

    const messages = await client.getMessages({ channel: "gmail" });
    expect(messages.items).toHaveLength(1);
    expect(messages.items[0]?.subject).toBe("Re: Principal AI Architect");
  });

  it("reads interview debriefs and individual debrief", async () => {
    const { syntheticInterviewDebriefPage } = await import("./fixtures.js");
    const transport = new RecordingTransport([
      graphqlData("interviewDebriefs", syntheticInterviewDebriefPage),
      graphqlData("interviewDebrief", syntheticInterviewDebriefPage.items[0]),
    ]);
    const client = createClient(transport);

    const debriefs = await client.getInterviewDebriefs({ opportunityId: "opp-synthetic-001" });
    expect(debriefs.items).toHaveLength(1);
    expect(debriefs.items[0]?.metadata.company).toBe("SoundHound");

    const debrief = await client.getInterviewDebrief("debrief-synthetic-001");
    expect(debrief?.fitAssessment.overallScore).toBe(94);
    expect(debrief?.actionItems[0]?.priority).toBe("P0");
  });
});

