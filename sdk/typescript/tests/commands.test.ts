import { describe, expect, expectTypeOf, it } from "vitest";

import {
  JOB_SEARCH_COMMAND_NAMES,
  UltradexAuthError,
  UltradexClient,
  UltradexHttpError,
  UltradexSchemaError,
  UltradexTimeoutError,
  UltradexTransportTimeout,
  type ContractHandle,
  type JobSearchCommand,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "../src/index.js";
import {
  syntheticContractHandleResponse,
  syntheticRefusedContractHandleResponse,
} from "./fixtures.js";

class RecordingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  constructor(private readonly responses: UltradexTransportResponse[]) {}

  async request(request: UltradexRequest): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    const response = this.responses.shift();
    if (response === undefined) {
      throw new Error("Synthetic transport queue exhausted");
    }
    return response;
  }
}

class RejectingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  constructor(private readonly error: unknown) {}

  async request(request: UltradexRequest): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    throw this.error;
  }
}

function response(status: number, body: unknown): UltradexTransportResponse {
  return {
    status,
    body: typeof body === "string" ? body : JSON.stringify(body),
  };
}

function createClient(transport: UltradexTransport): UltradexClient {
  return new UltradexClient({
    baseUrl: "https://ultradex.synthetic.example/",
    token: "synthetic-token",
    timeoutMs: 2_500,
    transport,
  });
}

describe("closed governed job-search command catalog", () => {
  it("publishes exactly the canonical command names and no raw escape hatch", () => {
    const client = createClient(new RecordingTransport([]));

    expect(JOB_SEARCH_COMMAND_NAMES).toEqual([
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
    ]);
    expect(client).not.toHaveProperty("submitJobSearchCommand");
    expectTypeOf<JobSearchCommand["commandName"]>().toEqualTypeOf<
      | "sources.ingest"
      | "opportunities.create"
      | "opportunities.score"
      | "applications.create"
      | "applications.transition"
      | "relationships.sync"
      | "outreach.prepare"
      | "outreach.approve"
      | "outreach.send"
      | "outreach.cancel"
      | "evidence.export"
      | "leads.create"
      | "leads.convert"
      | "organizations.create"
      | "organizations.update"
      | "workspace.initialize"
      | "intent.set"
    >();
  });

  it("sends literal parameters-only requests for all nine command methods", async () => {
    const transport = new RecordingTransport(
      Array.from({ length: 9 }, () =>
        response(202, syntheticContractHandleResponse),
      ),
    );
    const client = createClient(transport);
    const commitment =
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

    const handles = await Promise.all([
      client.submitSourcesIngest(
        {
          sourceKind: "web",
          sourceRef: "web-source-synthetic-001",
          observedAt: "2026-07-29T12:00:00+00:00",
        },
        { idempotencyKey: "idempotency-sources-ingest" },
      ),
      client.submitOpportunityCreate(
        {
          employer: "Synthetic Systems",
          title: "Platform Engineer",
          sourceEvidenceId: "evidence-synthetic-001",
        },
        {
          idempotencyKey: "idempotency-opportunity-create",
          delegationId: "delegation-synthetic-001",
          correlationId: "correlation-synthetic-001",
        },
      ),
      client.submitOpportunityScore(
        {
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        },
        { idempotencyKey: "idempotency-opportunity-score" },
      ),
      client.submitApplicationTransition(
        {
          applicationId: "application-synthetic-001",
          status: "interviewing",
          occurredAt: "2026-07-29T12:01:00+00:00",
        },
        { idempotencyKey: "idempotency-application-transition" },
      ),
      client.submitRelationshipSync(
        {
          opportunityId: "opportunity-synthetic-001",
          dexContactRef: "dex-contact-synthetic-001",
        },
        { idempotencyKey: "idempotency-relationship-sync" },
      ),
      client.submitOutreachPrepare(
        {
          opportunityId: "opportunity-synthetic-001",
          channel: "gmail",
          messageCommitment: commitment,
          relationshipId: "relationship-synthetic-001",
        },
        { idempotencyKey: "idempotency-outreach-prepare" },
      ),
      client.submitOutreachApprove(
        {
          outreachId: "outreach-synthetic-001",
          messageCommitment: commitment,
        },
        { idempotencyKey: "idempotency-outreach-approve" },
      ),
      client.submitOutreachSend(
        {
          outreachId: "outreach-synthetic-001",
          approvalContractId: "approval-synthetic-001",
          messageCommitment: commitment,
          channel: "linkedin",
        },
        { idempotencyKey: "idempotency-outreach-send" },
      ),
      client.submitEvidenceExport(
        {
          subjectType: "opportunity",
          subjectId: "opportunity-synthetic-001",
          profile: "accountability.v1",
        },
        { idempotencyKey: "idempotency-evidence-export" },
      ),
    ]);

    expectTypeOf(handles).toEqualTypeOf<ContractHandle[]>();
    expect(handles).toHaveLength(9);
    expect(transport.requests).toEqual([
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/sources.ingest",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-sources-ingest",
        },
        body:
          "{\"source_kind\":\"web\",\"source_ref\":\"web-source-synthetic-001\",\"observed_at\":\"2026-07-29T12:00:00+00:00\"}",
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/opportunities.create",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-opportunity-create",
          "X-Correlation-Id": "correlation-synthetic-001",
          "X-Delegation-Id": "delegation-synthetic-001",
        },
        body:
          "{\"employer\":\"Synthetic Systems\",\"title\":\"Platform Engineer\",\"source_evidence_id\":\"evidence-synthetic-001\"}",
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/opportunities.score",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-opportunity-score",
        },
        body:
          "{\"opportunity_id\":\"opportunity-synthetic-001\",\"lens\":\"executive\"}",
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/applications.transition",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-application-transition",
        },
        body:
          "{\"application_id\":\"application-synthetic-001\",\"status\":\"interviewing\",\"occurred_at\":\"2026-07-29T12:01:00+00:00\"}",
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/relationships.sync",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-relationship-sync",
        },
        body:
          "{\"opportunity_id\":\"opportunity-synthetic-001\",\"dex_contact_ref\":\"dex-contact-synthetic-001\"}",
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/outreach.prepare",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-outreach-prepare",
        },
        body:
          `{"opportunity_id":"opportunity-synthetic-001","channel":"gmail","message_commitment":"${commitment}","relationship_id":"relationship-synthetic-001"}`,
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/outreach.approve",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-outreach-approve",
        },
        body:
          `{"outreach_id":"outreach-synthetic-001","message_commitment":"${commitment}"}`,
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/outreach.send",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-outreach-send",
        },
        body:
          `{"outreach_id":"outreach-synthetic-001","approval_contract_id":"approval-synthetic-001","message_commitment":"${commitment}","channel":"linkedin"}`,
        timeoutMs: 2_500,
      },
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/evidence.export",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-evidence-export",
        },
        body:
          "{\"subject_type\":\"opportunity\",\"subject_id\":\"opportunity-synthetic-001\",\"profile\":\"accountability.v1\"}",
        timeoutMs: 2_500,
      },
    ]);
  });

  it("rejects empty idempotency keys before network I/O", async () => {
    const transport = new RecordingTransport([]);
    const client = createClient(transport);

    await expect(
      client.submitOpportunityScore(
        {
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        },
        { idempotencyKey: "   " },
      ),
    ).rejects.toThrow("idempotencyKey must be non-empty");
    expect(transport.requests).toEqual([]);
  });

  it("omits optional outreach relationship and governance headers", async () => {
    const transport = new RecordingTransport([
      response(202, syntheticContractHandleResponse),
    ]);
    const client = createClient(transport);

    await client.submitOutreachPrepare(
      {
        opportunityId: "opportunity-synthetic-001",
        channel: "manual",
        messageCommitment:
          "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      },
      { idempotencyKey: "idempotency-prepare-without-optionals" },
    );

    expect(transport.requests).toEqual([
      {
        method: "POST",
        url:
          "https://ultradex.synthetic.example/api/v2/job-search/commands/outreach.prepare",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
          "Idempotency-Key": "idempotency-prepare-without-optionals",
        },
        body:
          "{\"opportunity_id\":\"opportunity-synthetic-001\",\"channel\":\"manual\",\"message_commitment\":\"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\"}",
        timeoutMs: 2_500,
      },
    ]);
  });
});

describe("governed command outcomes", () => {
  it("preserves completion ambiguity when a governed command transport times out", async () => {
    const timeout = new UltradexTransportTimeout(2_500, true);
    const transport = new RejectingTransport(timeout);
    const client = createClient(transport);

    const pending = client.submitOpportunityScore(
      {
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      },
      {
        idempotencyKey: "idempotency-timeout-synthetic",
        correlationId: "correlation-timeout-synthetic",
      },
    );

    await expect(pending).rejects.toMatchObject({
      name: "UltradexTimeoutError",
      code: "timeout",
      timeoutMs: 2_500,
      requestMayHaveCompleted: true,
      cause: timeout,
    });
    await expect(pending).rejects.toBeInstanceOf(UltradexTimeoutError);
    expect(transport.requests).toHaveLength(1);
  });

  it("returns validated accepted, failed, unverifiable, and refused handles from 202 and 503", async () => {
    const failed = {
      ...syntheticContractHandleResponse,
      status: "failed",
    };
    const unverifiable = {
      ...syntheticContractHandleResponse,
      status: "unverifiable",
    };
    const transport = new RecordingTransport([
      response(202, syntheticContractHandleResponse),
      response(202, failed),
      response(503, unverifiable),
      response(503, syntheticRefusedContractHandleResponse),
    ]);
    const client = createClient(transport);
    const input = {
      opportunityId: "opportunity-synthetic-001",
      lens: "executive",
    } as const;

    const acceptedHandle = await client.submitOpportunityScore(input, {
      idempotencyKey: "idempotency-accepted",
    });
    const failedHandle = await client.submitOpportunityScore(input, {
      idempotencyKey: "idempotency-failed",
    });
    const unverifiableHandle = await client.submitOpportunityScore(input, {
      idempotencyKey: "idempotency-unverifiable",
    });
    const refusedHandle = await client.submitOpportunityScore(input, {
      idempotencyKey: "idempotency-refused",
    });

    expect(acceptedHandle.status).toBe("accepted");
    expect(failedHandle.status).toBe("failed");
    expect(unverifiableHandle.status).toBe("unverifiable");
    expect(refusedHandle).toMatchObject({
      status: "refused",
      refusalCode: "synthetic_policy_denied",
      refusalReason: "Synthetic policy did not authorize this operation",
    });
  });

  it.each([401, 403] as const)(
    "keeps HTTP %i as a structured authentication error",
    async (status) => {
      const transport = new RecordingTransport([
        response(status, { detail: "Synthetic intent not accepted" }),
      ]);

      const pending = createClient(transport).submitOpportunityScore(
        {
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        },
        { idempotencyKey: `idempotency-error-${status}` },
      );

      await expect(pending).rejects.toMatchObject({
        name: "UltradexAuthError",
        code: "authentication",
        status,
        details: { detail: "Synthetic intent not accepted" },
      });
      await expect(pending).rejects.toBeInstanceOf(UltradexAuthError);
    },
  );

  it.each([409, 422] as const)(
    "keeps HTTP %i as a structured client error",
    async (status) => {
      const transport = new RecordingTransport([
        response(status, { detail: "Synthetic intent not accepted" }),
      ]);

      const pending = createClient(transport).submitOpportunityScore(
        {
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        },
        { idempotencyKey: `idempotency-error-${status}` },
      );

      await expect(pending).rejects.toMatchObject({
        name: "UltradexHttpError",
        code: "http",
        status,
        details: { detail: "Synthetic intent not accepted" },
      });
      await expect(pending).rejects.toBeInstanceOf(UltradexHttpError);
    },
  );

  it.each([202, 503] as const)(
    "rejects malformed governed HTTP %i bodies before returning public data",
    async (status) => {
      const transport = new RecordingTransport([
        response(status, {
          ...syntheticContractHandleResponse,
          status: "refused",
          refusal_code: null,
          refusal_reason: null,
        }),
      ]);

      const pending = createClient(transport).submitOpportunityScore(
        {
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        },
        { idempotencyKey: `idempotency-malformed-${status}` },
      );

      await expect(pending).rejects.toBeInstanceOf(UltradexSchemaError);
    },
  );

  it("submits leads and organizations CRM commands", async () => {
    const transport = new RecordingTransport([
      response(202, syntheticContractHandleResponse),
      response(202, syntheticContractHandleResponse),
      response(202, syntheticContractHandleResponse),
      response(202, syntheticContractHandleResponse),
    ]);
    const client = createClient(transport);

    const leadHandle = await client.submitLeadCreate(
      {
        employer: "Anthropic",
        title: "Principal AI Architect",
        fitScore: 94.5,
      },
      { idempotencyKey: "idempotency-lead-create" },
    );
    expect(leadHandle.status).toBe("accepted");

    const convertHandle = await client.submitLeadConvert(
      {
        leadId: "lead-synthetic-001",
        stage: "interviewing",
      },
      { idempotencyKey: "idempotency-lead-convert" },
    );
    expect(convertHandle.status).toBe("accepted");

    const orgHandle = await client.submitOrganizationCreate(
      {
        name: "Anthropic",
        industry: "AI Research",
        advocacyRating: 95,
      },
      { idempotencyKey: "idempotency-org-create" },
    );
    expect(orgHandle.status).toBe("accepted");

    const orgUpdateHandle = await client.submitOrganizationUpdate(
      {
        organizationId: "org-synthetic-anthropic",
        notes: "Updated mission alignment notes.",
      },
      { idempotencyKey: "idempotency-org-update" },
    );
    expect(orgUpdateHandle.status).toBe("accepted");

    expect(transport.requests).toHaveLength(4);
    expect(transport.requests[0]?.url).toBe(
      "https://ultradex.synthetic.example/api/v2/job-search/commands/leads.create",
    );
    expect(transport.requests[1]?.url).toBe(
      "https://ultradex.synthetic.example/api/v2/job-search/commands/leads.convert",
    );
    expect(transport.requests[2]?.url).toBe(
      "https://ultradex.synthetic.example/api/v2/job-search/commands/organizations.create",
    );
    expect(transport.requests[3]?.url).toBe(
      "https://ultradex.synthetic.example/api/v2/job-search/commands/organizations.update",
    );
  });
});

