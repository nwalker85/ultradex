import {
  syntheticLifecycleEvent,
  syntheticOperation,
  syntheticOutreachPage,
} from "../../../sdk/typescript/tests/fixtures.js";
import {
  JOB_SEARCH_COMMAND_NAMES,
  UltradexClient,
  UltradexTransportTimeout,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "@ultradex/sdk";
import { describe, expect, test } from "vitest";

import {
  CommandController,
  isMutationAvailable,
} from "../src/mutations/command-controller.js";
import {
  COMMAND_CUSTODY_SECRET_ID,
  CommandCustodyJournal,
} from "../src/mutations/command-custody-journal.js";
import { COMMAND_FORMS } from "../src/mutations/command-forms.js";
import { OperationTracker } from "../src/mutations/operation-tracker.js";
import type { ObsidianSecretStorage } from "../src/settings.js";
import {
  SyntheticProjectionTransport,
  createProjectionStore,
} from "./synthetic-projection-client.js";

const ACCEPTED_HANDLE = {
  contract_id: "contract-controller-synthetic-001",
  operation_id: "operation-controller-synthetic-001",
  status: "accepted",
  submitted_at: "2026-07-29T16:00:00+00:00",
  correlation_id: "correlation-controller-synthetic-001",
  refusal_code: null,
  refusal_reason: null,
  expires_at: null,
  status_url: "/operations/operation-controller-synthetic-001",
  events_url: "/operations/operation-controller-synthetic-001/events",
} as const;

class CommandRecordingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    return {
      status: 202,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(ACCEPTED_HANDLE),
    };
  }
}

class PollingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    if (request.method === "POST" && !request.url.endsWith("/graphql")) {
      return {
        status: 202,
        headers: { "content-type": "application/json" },
        body: JSON.stringify(ACCEPTED_HANDLE),
      };
    }
    const body = JSON.parse(request.body ?? "{}") as {
      readonly query?: string;
    };
    const data = body.query?.includes("GetOperationEvents")
      ? {
          events: [
            {
              ...syntheticLifecycleEvent,
              operationId: ACCEPTED_HANDLE.operation_id,
            },
          ],
        }
      : {
          operation: {
            ...syntheticOperation,
            id: ACCEPTED_HANDLE.operation_id,
            correlationId: ACCEPTED_HANDLE.correlation_id,
            command: "opportunities.create",
          },
        };
    return {
      status: 200,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ data }),
    };
  }
}

class GovernedHandleTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  constructor(
    private readonly status: "refused" | "failed" | "unverifiable",
  ) {}

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    const body =
      this.status === "refused"
        ? {
            ...ACCEPTED_HANDLE,
            status: "refused",
            refusal_code: "synthetic_policy_denied",
            refusal_reason:
              "Synthetic policy did not authorize this operation",
          }
        : {
            ...ACCEPTED_HANDLE,
            status: this.status,
          };
    return {
      status: this.status === "refused" ? 503 : 202,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    };
  }
}

class AmbiguousTimeoutTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    throw new UltradexTransportTimeout(10_000, true);
  }
}

class SensitiveFailureTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    throw new Error(
      "Synthetic raw GraphQL detail token=synthetic-secret-must-not-render",
    );
  }
}

class MemoryCustodyStorage implements ObsidianSecretStorage {
  value: string | null = null;

  getSecret(id: string): string | null {
    return id === COMMAND_CUSTODY_SECRET_ID ? this.value : null;
  }

  setSecret(id: string, secret: string): void {
    if (id === COMMAND_CUSTODY_SECRET_ID) {
      this.value = secret;
    }
  }
}

class FailingWriteCustodyStorage extends MemoryCustodyStorage {
  writeAttempts = 0;

  constructor(private readonly failedWrites: readonly number[]) {
    super();
  }

  override setSecret(id: string, secret: string): void {
    this.writeAttempts += 1;
    if (this.failedWrites.includes(this.writeAttempts)) {
      throw new Error(
        `Synthetic custody write ${this.writeAttempts} failure`,
      );
    }
    super.setSecret(id, secret);
  }
}

class CustodyInspectingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];
  custodyAtRequest: unknown = null;
  release: (() => void) | null = null;
  private readonly gate = new Promise<void>((resolve) => {
    this.release = resolve;
  });

  constructor(private readonly storage: MemoryCustodyStorage) {}

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    if (request.url.endsWith("/api/graphql")) {
      throw new Error("Tracking must not begin after disposal");
    }
    this.custodyAtRequest = JSON.parse(this.storage.value ?? "{}");
    await this.gate;
    return {
      status: 202,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        ...ACCEPTED_HANDLE,
        status: "succeeded",
        submitted_at: "2026-07-29T17:00:01.000Z",
      }),
    };
  }
}

class GatedAmbiguousTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];
  release: (() => void) | null = null;
  private readonly gate = new Promise<void>((resolve) => {
    this.release = resolve;
  });

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    await this.gate;
    throw new UltradexTransportTimeout(10_000, true);
  }
}

class ImmediateHandleTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  constructor(
    private readonly status:
      | "pending"
      | "running"
      | "succeeded",
  ) {}

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    return {
      status: 202,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        ...ACCEPTED_HANDLE,
        status: this.status,
      }),
    };
  }
}

class DirectTerminalPollingTransport extends PollingTransport {
  override async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    if (!request.url.endsWith("/api/graphql")) {
      this.requests.push(request);
      return {
        status: 202,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          ...ACCEPTED_HANDLE,
          status: "succeeded",
        }),
      };
    }
    return super.request(request);
  }
}

async function readyProjectionStore() {
  const transport = new SyntheticProjectionTransport();
  transport.setAllFresh();
  transport.outreachItemsOverride = [
    {
      ...syntheticOutreachPage.items[0],
      status: "pending_approval",
      approvalContractId: null,
    },
  ];
  const store = createProjectionStore(transport);
  await store.refresh();
  return store;
}

describe("CommandController", () => {
  test.each([
    [
      [],
      "Refresh projections and review an outreach item that is awaiting approval.",
    ],
    [
      [
        {
          ...syntheticOutreachPage.items[0],
          status: "pending_approval",
          messageCommitment:
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          approvalContractId: null,
        },
      ],
      "The verified outreach binding does not match this approval request. Refresh projections and review it again.",
    ],
    [
      [
        {
          ...syntheticOutreachPage.items[0],
          status: "approved",
        },
      ],
      "The verified outreach binding does not match this approval request. Refresh projections and review it again.",
    ],
  ] as const)(
    "outreach approval rejects a missing, mismatched, or non-pending verified record before confirmation",
    async (outreachItems, expectedGuidance) => {
      const projectionTransport = new SyntheticProjectionTransport();
      projectionTransport.setAllFresh();
      projectionTransport.outreachItemsOverride = outreachItems;
      const store = createProjectionStore(projectionTransport);
      await store.refresh();
      const commandTransport = new CommandRecordingTransport();
      const controller = new CommandController({
        client: new UltradexClient({
          baseUrl: "https://synthetic.invalid",
          token: "synthetic-secret-value",
          transport: commandTransport,
        }),
        projectionStore: store,
        createId: (kind) => `${kind}-approve-invalid-001`,
      });

      expect(() =>
        controller.prepare(
          COMMAND_FORMS.outreachApprove.create({
            outreachId: "outreach-synthetic-001",
            messageCommitment:
              "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          }),
        ),
      ).toThrow(expectedGuidance);
      expect(controller.getState().confirmation).toBeNull();
      expect(commandTransport.requests).toEqual([]);
    },
  );

  test("outreach approval binds the exact pending record and its verified channel", async () => {
    const transport = new CommandRecordingTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport,
      }),
      projectionStore: await readyProjectionStore(),
      createId: (kind) => `${kind}-approve-valid-001`,
    });

    const confirmation = controller.prepare(
      COMMAND_FORMS.outreachApprove.create({
        outreachId: "outreach-synthetic-001",
        messageCommitment:
          "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      }),
    );

    expect(confirmation.boundFields).toContainEqual({
      label: "Channel",
      value: "gmail",
    });
    await controller.confirm(confirmation.id);
    expect(transport.requests).toHaveLength(1);
  });

  test("outreach approval rechecks the exact projection binding immediately before submission", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    projectionTransport.outreachItemsOverride = [
      {
        ...syntheticOutreachPage.items[0],
        status: "pending_approval",
        approvalContractId: null,
      },
    ];
    const store = createProjectionStore(projectionTransport);
    await store.refresh();
    const commandTransport = new CommandRecordingTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport: commandTransport,
      }),
      projectionStore: store,
      createId: (kind) => `${kind}-approve-recheck-001`,
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.outreachApprove.create({
        outreachId: "outreach-synthetic-001",
        messageCommitment:
          "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      }),
    );
    projectionTransport.outreachItemsOverride = [
      {
        ...syntheticOutreachPage.items[0],
        status: "approved",
      },
    ];
    await store.refresh();

    await controller.confirm(confirmation.id);

    expect(commandTransport.requests).toEqual([]);
    expect(controller.getState().confirmation).toMatchObject({
      id: confirmation.id,
      bindingError:
        "The verified outreach binding changed. Refresh projections and start a fresh approval review.",
    });
    expect(JSON.stringify(controller.getState())).not.toContain(
      "synthetic-secret",
    );
  });

  test("one confirmed command invokes its matching SDK method exactly once even when confirmation is clicked twice", async () => {
    const transport = new CommandRecordingTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      createId: (kind) =>
        kind === "idempotency"
          ? "idempotency-controller-synthetic-001"
          : "correlation-controller-synthetic-001",
      now: () => new Date("2026-07-29T16:00:00.000Z"),
    });

    const confirmation = controller.prepare({
      commandName: "opportunities.create",
      parameters: {
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      },
    });
    await Promise.all([
      controller.confirm(confirmation.id),
      controller.confirm(confirmation.id),
    ]);

    expect(transport.requests).toHaveLength(1);
    expect(transport.requests[0]).toMatchObject({
      method: "POST",
      url:
        "https://synthetic.invalid/api/v2/job-search/commands/" +
        "opportunities.create",
      headers: {
        "Idempotency-Key": "idempotency-controller-synthetic-001",
        "X-Correlation-Id": "correlation-controller-synthetic-001",
      },
    });
    expect(transport.requests[0]?.body).toBe(
      JSON.stringify({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        source_evidence_id: "evidence-synthetic-001",
      }),
    );
  });

  test("operation and event polling remain read-only and cannot resubmit the confirmed command", async () => {
    const transport = new PollingTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 1,
        pollIntervalMs: 1,
      }),
      createId: (kind) =>
        kind === "idempotency"
          ? "idempotency-controller-polling-001"
          : "correlation-controller-polling-001",
      now: () => new Date("2026-07-29T16:01:00.000Z"),
    });

    const confirmation = controller.prepare({
      commandName: "opportunities.create",
      parameters: {
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      },
    });
    await controller.confirm(confirmation.id);

    expect(
      transport.requests.filter(
        (request) =>
          request.method === "POST" &&
          !request.url.endsWith("/graphql"),
      ),
    ).toHaveLength(1);
    expect(
      transport.requests.filter((request) =>
        request.url.endsWith("/graphql"),
      ),
    ).toHaveLength(2);
    expect(controller.getState().records[0]).toMatchObject({
      commandName: "opportunities.create",
      operationId: ACCEPTED_HANDLE.operation_id,
      state: "unverifiable",
    });
  });

  test("refused, failed, and unverifiable handles retain distinct governed outcomes and server evidence", async () => {
    const records = [];
    for (const status of [
      "refused",
      "failed",
      "unverifiable",
    ] as const) {
      const transport = new GovernedHandleTransport(status);
      const controller = new CommandController({
        client: new UltradexClient({
          baseUrl: "https://synthetic.invalid",
          token: "synthetic-secret-value",
          transport,
        }),
        projectionStore: await readyProjectionStore(),
        createId: (kind) => `${kind}-controller-${status}-001`,
        now: () => new Date("2026-07-29T16:02:00.000Z"),
      });
      const confirmation = controller.prepare({
        commandName: "opportunities.create",
        parameters: {
          employer: "Synthetic Systems",
          title: "Platform Engineer",
          sourceEvidenceId: "evidence-synthetic-001",
        },
      });

      await controller.confirm(confirmation.id);
      records.push(controller.getState().records[0]);
    }

    expect(records).toEqual([
      expect.objectContaining({
        state: "refused",
        operationId: ACCEPTED_HANDLE.operation_id,
        correlationId: "correlation-controller-refused-001",
        serverReasonCode: "synthetic_policy_denied",
        serverReason:
          "Synthetic policy did not authorize this operation",
      }),
      expect.objectContaining({
        state: "failed",
        operationId: ACCEPTED_HANDLE.operation_id,
        correlationId: "correlation-controller-failed-001",
      }),
      expect.objectContaining({
        state: "unverifiable",
        operationId: ACCEPTED_HANDLE.operation_id,
        correlationId: "correlation-controller-unverifiable-001",
      }),
    ]);
  });

  test("an ambiguous pre-handle timeout retains completion-unknown evidence and blocks resubmission", async () => {
    const transport = new AmbiguousTimeoutTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport,
      }),
      projectionStore: await readyProjectionStore(),
      createId: (kind) =>
        kind === "idempotency"
          ? "idempotency-controller-timeout-001"
          : "correlation-controller-timeout-001",
      now: () => new Date("2026-07-29T16:03:00.000Z"),
    });
    const confirmation = controller.prepare({
      commandName: "opportunities.create",
      parameters: {
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      },
    });

    await controller.confirm(confirmation.id);
    await controller.confirm(confirmation.id);

    expect(transport.requests).toHaveLength(1);
    expect(controller.getState()).toMatchObject({
      confirmation: null,
      records: [
        {
          commandName: "opportunities.create",
          idempotencyKey: "idempotency-controller-timeout-001",
          correlationId: "correlation-controller-timeout-001",
          submittedAt: "2026-07-29T16:03:00.000Z",
          contractId: null,
          operationId: null,
          state: "unverifiable",
          completionUnknown: true,
          resubmissionBlocked: true,
          events: [],
        },
      ],
    });
  });

  test("all nine explicit typed forms dispatch only to their matching SDK command methods", async () => {
    const transport = new CommandRecordingTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport,
      }),
      projectionStore: await readyProjectionStore(),
      createId: (kind) => `${kind}-controller-catalog-001`,
      now: () => new Date("2026-07-29T16:04:00.000Z"),
    });
    const commitment =
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const drafts = [
      COMMAND_FORMS.sourcesIngest.create({
        sourceKind: "manual",
        sourceRef: "manual-synthetic-001",
        observedAt: "2026-07-29T16:04:00+00:00",
      }),
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
      COMMAND_FORMS.applicationTransition.create({
        applicationId: "application-synthetic-001",
        status: "interviewing",
        occurredAt: "2026-07-29T16:04:00+00:00",
      }),
      COMMAND_FORMS.relationshipSync.create({
        opportunityId: "opportunity-synthetic-001",
        dexContactRef: "dex-synthetic-001",
      }),
      COMMAND_FORMS.outreachPrepare.create({
        opportunityId: "opportunity-synthetic-001",
        channel: "linkedin",
        messageCommitment: commitment,
        relationshipId: "relationship-synthetic-001",
      }),
      COMMAND_FORMS.outreachApprove.create({
        outreachId: "outreach-synthetic-001",
        messageCommitment: commitment,
      }),
      COMMAND_FORMS.outreachSend.create({
        outreachId: "outreach-synthetic-001",
        approvalContractId: "approval-synthetic-001",
        messageCommitment: commitment,
        channel: "linkedin",
      }),
      COMMAND_FORMS.evidenceExport.create({
        subjectType: "opportunity",
        subjectId: "opportunity-synthetic-001",
        profile: "accountability.v1",
      }),
    ] as const;

    expect(drafts.map(({ commandName }) => commandName)).toEqual(
      JOB_SEARCH_COMMAND_NAMES,
    );
    for (const draft of drafts) {
      const confirmation = controller.prepare(draft);
      await controller.confirm(confirmation.id);
      if (draft.commandName === "outreach.send") {
        await controller.confirmOutreachSend(
          confirmation.id,
          draft.parameters.approvalContractId,
        );
      }
    }

    expect(
      transport.requests.map((request) => [
        request.url.replace(
          "https://synthetic.invalid/api/v2/job-search/commands/",
          "",
        ),
        request.body,
      ]),
    ).toEqual([
      [
        "sources.ingest",
        '{"source_kind":"manual","source_ref":"manual-synthetic-001","observed_at":"2026-07-29T16:04:00+00:00"}',
      ],
      [
        "opportunities.create",
        '{"employer":"Synthetic Systems","title":"Platform Engineer","source_evidence_id":"evidence-synthetic-001"}',
      ],
      [
        "opportunities.score",
        '{"opportunity_id":"opportunity-synthetic-001","lens":"executive"}',
      ],
      [
        "applications.transition",
        '{"application_id":"application-synthetic-001","status":"interviewing","occurred_at":"2026-07-29T16:04:00+00:00"}',
      ],
      [
        "relationships.sync",
        '{"opportunity_id":"opportunity-synthetic-001","dex_contact_ref":"dex-synthetic-001"}',
      ],
      [
        "outreach.prepare",
        `{"opportunity_id":"opportunity-synthetic-001","channel":"linkedin","message_commitment":"${commitment}","relationship_id":"relationship-synthetic-001"}`,
      ],
      [
        "outreach.approve",
        `{"outreach_id":"outreach-synthetic-001","message_commitment":"${commitment}"}`,
      ],
      [
        "outreach.send",
        `{"outreach_id":"outreach-synthetic-001","approval_contract_id":"approval-synthetic-001","message_commitment":"${commitment}","channel":"linkedin"}`,
      ],
      [
        "evidence.export",
        '{"subject_type":"opportunity","subject_id":"opportunity-synthetic-001","profile":"accountability.v1"}',
      ],
    ]);
  });

  test("outreach send requires a second confirmation carrying the exact approval contract ID", async () => {
    const transport = new CommandRecordingTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport,
      }),
      projectionStore: await readyProjectionStore(),
      createId: (kind) => `${kind}-controller-send-001`,
      now: () => new Date("2026-07-29T16:06:00.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.outreachSend.create({
        outreachId: "outreach-synthetic-001",
        approvalContractId: "approval-synthetic-exact-001",
        messageCommitment:
          "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        channel: "linkedin",
      }),
    );

    await controller.confirm(confirmation.id);
    expect(transport.requests).toEqual([]);
    expect(controller.getState().confirmation).toMatchObject({
      id: confirmation.id,
      stage: "awaiting-second-confirmation",
    });

    await controller.confirmOutreachSend(
      confirmation.id,
      "approval-synthetic-wrong-001",
    );
    expect(transport.requests).toEqual([]);

    await controller.confirmOutreachSend(
      confirmation.id,
      "approval-synthetic-exact-001",
    );
    expect(transport.requests).toHaveLength(1);
    expect(transport.requests[0]?.body).toContain(
      '"approval_contract_id":"approval-synthetic-exact-001"',
    );
  });

  test("idle, loading, authentication, offline, invalid, degraded, and cleared projection states are read-only", async () => {
    let releaseLoading: (() => void) | undefined;
    const loadingGate = new Promise<void>((resolve) => {
      releaseLoading = resolve;
    });
    const loadingTransport = new SyntheticProjectionTransport(loadingGate);
    loadingTransport.setAllFresh();
    const loadingStore = createProjectionStore(loadingTransport);
    const loadingRefresh = loadingStore.refresh();

    const authenticationTransport = new SyntheticProjectionTransport();
    authenticationTransport.failureMode = "authentication";
    const authenticationStore = createProjectionStore(
      authenticationTransport,
    );
    await authenticationStore.refresh();

    const offlineTransport = new SyntheticProjectionTransport();
    offlineTransport.failureMode = "network";
    const offlineStore = createProjectionStore(offlineTransport);
    await offlineStore.refresh();

    const invalidTransport = new SyntheticProjectionTransport();
    invalidTransport.schemaFailureProjection = "applications";
    const invalidStore = createProjectionStore(invalidTransport);
    await invalidStore.refresh();

    const degradedTransport = new SyntheticProjectionTransport();
    const degradedStore = createProjectionStore(degradedTransport);
    await degradedStore.refresh();

    const clearedStore = await readyProjectionStore();
    clearedStore.clear();

    expect([
      isMutationAvailable(
        createProjectionStore(new SyntheticProjectionTransport()),
      ),
      isMutationAvailable(loadingStore),
      isMutationAvailable(authenticationStore),
      isMutationAvailable(offlineStore),
      isMutationAvailable(invalidStore),
      isMutationAvailable(degradedStore),
      isMutationAvailable(clearedStore),
    ]).toEqual([false, false, false, false, false, false, false]);

    releaseLoading?.();
    await loadingRefresh;
  });

  test("a state change after review prevents submission and leaves the reviewed attempt unavailable", async () => {
    const transport = new CommandRecordingTransport();
    const store = await readyProjectionStore();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport,
      }),
      projectionStore: store,
      createId: (kind) => `${kind}-controller-recheck-001`,
      now: () => new Date("2026-07-29T16:09:00.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );
    store.clear();

    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();

    expect(transport.requests).toEqual([]);
    expect(controller.getState().confirmation).toMatchObject({
      id: confirmation.id,
      stage: "awaiting-confirmation",
    });
  });

  test("transport failures become bounded failed evidence without raw GraphQL or secret details", async () => {
    const transport = new SensitiveFailureTransport();
    const storage = new MemoryCustodyStorage();
    const journal = new CommandCustodyJournal(storage);
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
      createId: (kind) => `${kind}-controller-failure-001`,
      now: () => new Date("2026-07-29T16:10:00.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );

    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();

    expect(controller.getState()).toMatchObject({
      confirmation: null,
      records: [
        {
          commandName: "opportunities.score",
          state: "failed",
          operationId: null,
          completionUnknown: false,
          resubmissionBlocked: true,
          localReason:
            "Ultradex did not accept this command attempt. Start a fresh form after checking connection and authentication state.",
        },
      ],
    });
    const visibleState = JSON.stringify(controller.getState());
    expect(visibleState).not.toContain("GraphQL");
    expect(visibleState).not.toContain("synthetic-secret");
    expect(visibleState).not.toContain("token=");
    expect(journal.load()).toEqual([]);

    const restarted = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restarted.getState().records).toEqual([]);
  });

  test("an initial custody write failure prevents command submission and exposes only local failed evidence", async () => {
    const storage = new FailingWriteCustodyStorage([1]);
    const journal = new CommandCustodyJournal(storage);
    const transport = new CommandRecordingTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
      createId: (kind) => `${kind}-initial-custody-failure-001`,
      now: () => new Date("2026-07-29T16:10:15.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );

    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();
    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();

    expect(storage.writeAttempts).toBe(1);
    expect(transport.requests).toEqual([]);
    expect(controller.getState()).toMatchObject({
      confirmation: null,
      records: [
        {
          idempotencyKey:
            "idempotency-initial-custody-failure-001",
          state: "failed",
          contractId: null,
          operationId: null,
          completionUnknown: false,
          resubmissionBlocked: true,
          localReason:
            "Command was not sent because local command custody was unavailable. Start a fresh form after checking local storage.",
        },
      ],
    });
    expect(journal.load()).toEqual([]);

    const restarted = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restarted.getState().records).toEqual([]);
  });

  test("an ambiguous timeout with a failed second custody write remains completion-unknown across restart", async () => {
    const storage = new FailingWriteCustodyStorage([2]);
    const journal = new CommandCustodyJournal(storage);
    const transport = new AmbiguousTimeoutTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
      createId: (kind) => `${kind}-ambiguous-custody-failure-001`,
      now: () => new Date("2026-07-29T16:10:20.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );

    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();
    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();

    expect(storage.writeAttempts).toBe(2);
    expect(transport.requests).toHaveLength(1);
    expect(controller.getState().records).toEqual([
      expect.objectContaining({
        state: "unverifiable",
        contractId: null,
        operationId: null,
        completionUnknown: true,
        resubmissionBlocked: true,
      }),
    ]);
    expect(journal.load()).toEqual([
      expect.objectContaining({
        idempotencyKey:
          "idempotency-ambiguous-custody-failure-001",
        state: "submitting",
      }),
    ]);

    const restarted = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restarted.getState().records).toEqual([
      expect.objectContaining({
        state: "unverifiable",
        operationId: null,
        completionUnknown: true,
        resubmissionBlocked: true,
      }),
    ]);
  });

  test("a returned terminal handle with a failed second custody write retains identifiers but not a durable success claim", async () => {
    const storage = new FailingWriteCustodyStorage([2]);
    const journal = new CommandCustodyJournal(storage);
    const transport = new ImmediateHandleTransport("succeeded");
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
      createId: (kind) => `${kind}-handle-custody-failure-001`,
      now: () => new Date("2026-07-29T16:10:25.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );

    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();
    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();

    expect(storage.writeAttempts).toBe(2);
    expect(transport.requests).toHaveLength(1);
    expect(controller.getState().records).toEqual([
      expect.objectContaining({
        state: "unverifiable",
        contractId: ACCEPTED_HANDLE.contract_id,
        operationId: ACCEPTED_HANDLE.operation_id,
        completionUnknown: true,
        resubmissionBlocked: true,
      }),
    ]);
    expect(journal.load()).toEqual([
      expect.objectContaining({
        idempotencyKey:
          "idempotency-handle-custody-failure-001",
        state: "submitting",
      }),
    ]);

    const restarted = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restarted.getState().records).toEqual([
      expect.objectContaining({
        state: "unverifiable",
        evidenceStatus: "unverifiable",
        contractId: null,
        operationId: null,
        completionUnknown: true,
        resubmissionBlocked: true,
      }),
    ]);
  });

  test("tracker custody write failures cannot reject confirmation or resubmit the command", async () => {
    const storage = new FailingWriteCustodyStorage([3, 4]);
    const journal = new CommandCustodyJournal(storage);
    const transport = new PollingTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 1,
        pollIntervalMs: 1,
      }),
      journal,
      createId: (kind) => `${kind}-tracker-custody-failure-001`,
      now: () => new Date("2026-07-29T16:10:27.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );

    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();
    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();

    expect(storage.writeAttempts).toBe(4);
    expect(
      transport.requests.filter(
        (request) =>
          request.method === "POST" &&
          !request.url.endsWith("/graphql"),
      ),
    ).toHaveLength(1);
    expect(controller.getState().records).toEqual([
      expect.objectContaining({
        state: "unverifiable",
        contractId: ACCEPTED_HANDLE.contract_id,
        operationId: ACCEPTED_HANDLE.operation_id,
        completionUnknown: true,
        resubmissionBlocked: true,
      }),
    ]);
  });

  test("a custody clear failure keeps the known rejection completion-unknown and blocked", async () => {
    const storage = new FailingWriteCustodyStorage([2]);
    const journal = new CommandCustodyJournal(storage);
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: new SensitiveFailureTransport(),
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
      createId: (kind) => `${kind}-controller-clear-failure-001`,
      now: () => new Date("2026-07-29T16:10:30.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );

    await expect(controller.confirm(confirmation.id)).resolves.toBeUndefined();

    expect(storage.writeAttempts).toBe(2);
    expect(controller.getState()).toMatchObject({
      confirmation: null,
      records: [
        {
          idempotencyKey:
            "idempotency-controller-clear-failure-001",
          state: "unverifiable",
          contractId: null,
          operationId: null,
          completionUnknown: true,
          resubmissionBlocked: true,
        },
      ],
    });
    expect(journal.load()).toEqual([
      expect.objectContaining({
        idempotencyKey:
          "idempotency-controller-clear-failure-001",
        state: "submitting",
      }),
    ]);

    const restarted = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restarted.getState().records).toEqual([
      expect.objectContaining({
        state: "unverifiable",
        completionUnknown: true,
        resubmissionBlocked: true,
      }),
    ]);
  });

  test("writes submitting custody with the actual attempt time before the network call and restores an interrupted attempt as completion unknown", async () => {
    const storage = new MemoryCustodyStorage();
    const journal = new CommandCustodyJournal(storage);
    const transport = new CustodyInspectingTransport(storage);
    const instants = [
      new Date("2026-07-29T17:00:00.000Z"),
      new Date("2026-07-29T17:00:01.000Z"),
    ];
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport,
      }),
      projectionStore: await readyProjectionStore(),
      journal,
      createId: (kind) => `${kind}-custody-synthetic-001`,
      now: () => instants.shift() ?? new Date("2026-07-29T17:00:01.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );

    const submission = controller.confirm(confirmation.id);
    await Promise.resolve();

    expect(transport.custodyAtRequest).toEqual({
      version: 1,
      entries: [
        {
          commandName: "opportunities.create",
          idempotencyKey: "idempotency-custody-synthetic-001",
          correlationId: "correlation-custody-synthetic-001",
          submittedAt: "2026-07-29T17:00:01.000Z",
          contractId: null,
          operationId: null,
          approvalContractId: null,
          state: "submitting",
        },
      ],
    });
    const restarted = new CommandController({
      client: new ImmediateHandleTransport("succeeded") as never,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restarted.getState().records).toEqual([
      expect.objectContaining({
        commandName: "opportunities.create",
        submittedAt: "2026-07-29T17:00:01.000Z",
        state: "unverifiable",
        completionUnknown: true,
        resubmissionBlocked: true,
        operationId: null,
      }),
    ]);

    controller.stopTracking();
    transport.release?.();
    await submission;
  });

  test("a stopped controller performs no post-handle reads or notifications but safely journals the returned handle for a new instance", async () => {
    const storage = new MemoryCustodyStorage();
    const journal = new CommandCustodyJournal(storage);
    const transport = new CustodyInspectingTransport(storage);
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      operationTracker: new OperationTracker(client),
      journal,
      createId: (kind) => `${kind}-dispose-synthetic-001`,
      now: () => new Date("2026-07-29T17:01:00.000Z"),
    });
    let notifications = 0;
    controller.subscribe(() => {
      notifications += 1;
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );
    const submission = controller.confirm(confirmation.id);
    await Promise.resolve();
    controller.stopTracking();
    const notificationsAtStop = notifications;

    transport.release?.();
    await submission;

    expect(transport.requests).toHaveLength(1);
    expect(notifications).toBe(notificationsAtStop);
    const restored = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restored.getState().records[0]).toMatchObject({
      state: "succeeded",
      evidenceStatus: "pending",
      contractId: "contract-controller-synthetic-001",
      operationId: "operation-controller-synthetic-001",
      submittedAt: "2026-07-29T17:00:01.000Z",
    });
  });

  test("an ambiguous timeout completing after stop updates only custody and never the disposed controller state", async () => {
    const storage = new MemoryCustodyStorage();
    const journal = new CommandCustodyJournal(storage);
    const transport = new GatedAmbiguousTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport,
      }),
      projectionStore: await readyProjectionStore(),
      journal,
      createId: (kind) => `${kind}-disposed-timeout-synthetic-001`,
      now: () => new Date("2026-07-29T17:01:30.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );
    const submission = controller.confirm(confirmation.id);
    await Promise.resolve();
    controller.stopTracking();

    transport.release?.();
    await submission;

    expect(controller.getState().records).toEqual([]);
    const restored = new CommandController({
      client: new ImmediateHandleTransport("succeeded") as never,
      projectionStore: await readyProjectionStore(),
      journal,
    });
    expect(restored.getState().records[0]).toMatchObject({
      state: "unverifiable",
      completionUnknown: true,
      resubmissionBlocked: true,
      operationId: null,
    });
  });

  test.each([
    ["pending", "pending"],
    ["running", "running"],
  ] as const)(
    "preserves a %s handle as a distinct %s governed outcome",
    async (handleStatus, expectedState) => {
      const transport = new ImmediateHandleTransport(handleStatus);
      const controller = new CommandController({
        client: new UltradexClient({
          baseUrl: "https://synthetic.invalid",
          token: "synthetic-secret-value",
          transport,
        }),
        projectionStore: await readyProjectionStore(),
        createId: (kind) => `${kind}-${handleStatus}-synthetic-001`,
        now: () => new Date("2026-07-29T17:02:00.000Z"),
      });
      const confirmation = controller.prepare(
        COMMAND_FORMS.opportunityScore.create({
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        }),
      );

      await controller.confirm(confirmation.id);

      expect(controller.getState().records[0]?.state).toBe(
        expectedState,
      );
    },
  );

  test("a direct terminal handle with an operation ID resolves lifecycle and receipt evidence", async () => {
    const transport = new DirectTerminalPollingTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport,
    });
    const controller = new CommandController({
      client,
      projectionStore: await readyProjectionStore(),
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 1,
      }),
      createId: (kind) => `${kind}-terminal-handle-synthetic-001`,
      now: () => new Date("2026-07-29T17:03:00.000Z"),
    });
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );

    await controller.confirm(confirmation.id);

    expect(
      transport.requests.filter((request) =>
        request.url.endsWith("/api/graphql"),
      ),
    ).not.toEqual([]);
  });
});
