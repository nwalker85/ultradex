import {
  syntheticApprovalEvidence,
  syntheticCompletedOperation,
  syntheticExecutionReceiptEvidence,
  syntheticLifecycleEvent,
  syntheticOperation,
} from "../../../sdk/typescript/tests/fixtures.js";
import {
  UltradexClient,
  type OperationStatus,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "@ultradex/sdk";
import {
  afterEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";

import {
  type GovernedMutationRecord,
  OperationTracker,
} from "../src/mutations/operation-tracker.js";

function seedRecord(
  operationId = "operation-synthetic-001",
): GovernedMutationRecord {
  return {
    id: "idempotency-tracker-synthetic-001",
    commandName: "outreach.send",
    consequence: "Synthetic approval-bound send.",
    submittedAt: "2026-07-29T16:07:00.000Z",
    idempotencyKey: "idempotency-tracker-synthetic-001",
    correlationId: "correlation-tracker-synthetic-001",
    contractId: "contract-tracker-synthetic-001",
    operationId,
    state: "accepted",
    evidenceStatus: "pending",
    serverReasonCode: null,
    serverReason: null,
    localReason: null,
    completionUnknown: false,
    resubmissionBlocked: true,
    events: [],
    approvalContractId: "approval-synthetic-001",
    approval: null,
    receipt: null,
    localSignatureVerification: "unavailable",
  };
}

interface GraphQLCall {
  readonly name: string;
  readonly variables: Readonly<Record<string, unknown>>;
}

class TrackerTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];
  readonly calls: GraphQLCall[] = [];
  operationStatuses: OperationStatus[] = ["running"];
  operationResults: unknown[] = [];
  operationErrors: Array<string | null> = [];
  activeRequests = 0;
  maxActiveRequests = 0;
  failWithSensitiveDetail = false;
  approvalAvailable = true;
  receiptAvailable = true;
  failExecutionReceiptRead = false;

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    this.activeRequests += 1;
    this.maxActiveRequests = Math.max(
      this.maxActiveRequests,
      this.activeRequests,
    );
    try {
      if (this.failWithSensitiveDetail) {
        throw new Error(
          "Synthetic raw GraphQL token=tracker-secret-must-not-render",
        );
      }
      const body = JSON.parse(request.body ?? "{}") as {
        readonly query?: string;
        readonly variables?: Readonly<Record<string, unknown>>;
      };
      const name = /query ([A-Za-z]+)/u.exec(body.query ?? "")?.[1];
      if (name === undefined) {
        throw new Error("Unexpected synthetic GraphQL request");
      }
      this.calls.push({
        name,
        variables: body.variables ?? {},
      });
      let data: unknown;
      if (name === "GetOperation") {
        const status = this.operationStatuses.shift() ?? "running";
        const operationResult =
          this.operationResults.length > 0
            ? this.operationResults.shift()
            : undefined;
        const operationError =
          this.operationErrors.length > 0
            ? this.operationErrors.shift()
            : undefined;
        const id = String(body.variables?.id);
        data = {
          operation:
            status === "completed"
              ? {
                  ...syntheticCompletedOperation,
                  id,
                  ...(operationResult === undefined
                    ? {}
                    : { result: operationResult }),
                  ...(operationError === undefined
                    ? {}
                    : { error: operationError }),
                }
              : {
                  ...syntheticOperation,
                  id,
                  status,
                  completedAt:
                    status === "failed" || status === "refused"
                      ? "2026-07-29T16:08:00+00:00"
                      : null,
                  error:
                    operationError === undefined
                      ? status === "failed"
                        ? "synthetic_execution_failure"
                        : status === "refused"
                          ? "synthetic_policy_denied"
                          : null
                      : operationError,
                },
        };
      } else if (name === "GetOperationEvents") {
        data = {
          events: [
            {
              ...syntheticLifecycleEvent,
              operationId: String(body.variables?.operationId),
            },
          ],
        };
      } else if (name === "GetApproval") {
        data = {
          approval: this.approvalAvailable
            ? syntheticApprovalEvidence
            : null,
        };
      } else if (name === "GetExecutionReceipt") {
        if (this.failExecutionReceiptRead) {
          throw new Error(
            "Synthetic raw receipt token=tracker-secret-must-not-render",
          );
        }
        data = {
          executionReceipt: this.receiptAvailable
            ? {
                ...syntheticExecutionReceiptEvidence,
                operationId: String(body.variables?.operationId),
              }
            : null,
        };
      } else {
        throw new Error(`Unexpected synthetic query ${name}`);
      }
      await Promise.resolve();
      return {
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ data }),
      };
    } finally {
      this.activeRequests -= 1;
    }
  }
}

class GatedTrackerTransport extends TrackerTransport {
  release: (() => void) | null = null;
  private readonly gate = new Promise<void>((resolve) => {
    this.release = resolve;
  });

  override async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    const body = JSON.parse(request.body ?? "{}") as {
      readonly query?: string;
    };
    if (body.query?.includes("GetOperation")) {
      await this.gate;
    }
    return super.request(request);
  }
}

function createTrackerClient(transport: UltradexTransport): UltradexClient {
  return new UltradexClient({
    baseUrl: "https://synthetic.invalid",
    token: "synthetic-secret-value",
    transport,
  });
}

afterEach(() => {
  vi.useRealTimers();
});

describe("OperationTracker", () => {
  test("polling is bounded and non-overlapping, preserves the operation ID on timeout, and manual refresh remains read-only", async () => {
    vi.useFakeTimers();
    const transport = new TrackerTransport();
    transport.operationStatuses = ["running", "running"];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 2,
      pollIntervalMs: 1_000,
    });
    const updates: GovernedMutationRecord[] = [];

    const tracking = tracker.track(seedRecord(), (record) => {
      updates.push(record);
    });
    const duplicateTracking = tracker.track(seedRecord(), (record) => {
      updates.push(record);
    });
    expect(duplicateTracking).toBe(tracking);
    await vi.advanceTimersByTimeAsync(0);
    expect(transport.calls.map(({ name }) => name)).toEqual([
      "GetOperation",
      "GetOperationEvents",
    ]);

    await vi.advanceTimersByTimeAsync(999);
    expect(transport.calls).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    await tracking;

    expect(transport.maxActiveRequests).toBe(1);
    expect(transport.calls.map(({ name }) => name)).toEqual([
      "GetOperation",
      "GetOperationEvents",
      "GetOperation",
      "GetOperationEvents",
    ]);
    const timedOut = updates.at(-1);
    expect(timedOut).toMatchObject({
      state: "unverifiable",
      evidenceStatus: "unverifiable",
      operationId: "operation-synthetic-001",
    });

    transport.operationStatuses = ["completed"];
    await tracker.refresh(timedOut!, (record) => {
      updates.push(record);
    });

    expect(updates.at(-1)).toMatchObject({
      state: "succeeded",
      evidenceStatus: "complete",
      operationId: "operation-synthetic-001",
    });
    expect(
      transport.requests.every(
        (request) =>
          request.method === "POST" &&
          request.url === "https://synthetic.invalid/api/graphql",
      ),
    ).toBe(true);
  });

  test("terminal tracking resolves approval by exact contract ID and receipt by unique operation ID as server-recorded evidence", async () => {
    const transport = new TrackerTransport();
    transport.operationStatuses = ["completed"];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 3,
      pollIntervalMs: 1,
    });
    const updates: GovernedMutationRecord[] = [];
    const operationId = "operation-synthetic-completed-001";

    await tracker.track(seedRecord(operationId), (record) => {
      updates.push(record);
    });

    expect(
      transport.calls.map(({ name, variables }) => ({
        name,
        variables,
      })),
    ).toEqual([
      {
        name: "GetOperation",
        variables: { id: operationId },
      },
      {
        name: "GetOperationEvents",
        variables: { operationId, first: 50 },
      },
      {
        name: "GetApproval",
        variables: { id: "approval-synthetic-001" },
      },
      {
        name: "GetExecutionReceipt",
        variables: { operationId },
      },
    ]);
    expect(updates.at(-1)).toMatchObject({
      state: "succeeded",
      evidenceStatus: "complete",
      approval: {
        approvalId: "approval-synthetic-001",
      },
      receipt: {
        operationId,
        proofStatus: "server-recorded",
        receiptHash:
          syntheticExecutionReceiptEvidence.receiptHash,
      },
      localSignatureVerification: "unavailable",
    });
  });

  test("stopAll cancels scheduled polls and suppresses late updates after view detach", async () => {
    vi.useFakeTimers();
    const transport = new TrackerTransport();
    transport.operationStatuses = ["running", "running"];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 5,
      pollIntervalMs: 1_000,
    });
    const updates: GovernedMutationRecord[] = [];
    const tracking = tracker.track(seedRecord(), (record) => {
      updates.push(record);
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(updates).toHaveLength(1);
    expect(vi.getTimerCount()).toBe(1);

    tracker.stopAll();

    expect(vi.getTimerCount()).toBe(0);
    await tracking;
    await vi.runAllTimersAsync();
    expect(transport.calls).toHaveLength(2);
    expect(updates).toHaveLength(1);
  });

  test("read failures become bounded unverifiable evidence without raw GraphQL or secret details", async () => {
    const transport = new TrackerTransport();
    transport.failWithSensitiveDetail = true;
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 2,
      pollIntervalMs: 1,
    });
    const updates: GovernedMutationRecord[] = [];

    await expect(
      tracker.track(seedRecord(), (record) => {
        updates.push(record);
      }),
    ).resolves.toBeUndefined();

    expect(updates).toEqual([
      expect.objectContaining({
        state: "unverifiable",
        evidenceStatus: "unverifiable",
        operationId: "operation-synthetic-001",
        localReason:
          "Operation evidence could not be refreshed. The operation ID is preserved for a later manual refresh.",
      }),
    ]);
    expect(JSON.stringify(updates)).not.toContain("GraphQL");
    expect(JSON.stringify(updates)).not.toContain("tracker-secret");
  });

  test("concurrent manual refreshes share one active operation read cycle", async () => {
    const transport = new TrackerTransport();
    transport.operationStatuses = ["running"];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 1,
      pollIntervalMs: 1,
    });
    const updates: GovernedMutationRecord[] = [];

    await Promise.all([
      tracker.refresh(seedRecord(), (record) => updates.push(record)),
      tracker.refresh(seedRecord(), (record) => updates.push(record)),
    ]);

    expect(transport.calls.map(({ name }) => name)).toEqual([
      "GetOperation",
      "GetOperationEvents",
    ]);
    expect(transport.maxActiveRequests).toBe(1);
    expect(updates).toHaveLength(1);
  });

  test("terminal operations retry missing required approval and receipt evidence, then remain manually refreshable by operation ID", async () => {
    vi.useFakeTimers();
    const transport = new TrackerTransport();
    transport.operationStatuses = ["completed", "completed"];
    transport.approvalAvailable = false;
    transport.receiptAvailable = false;
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 2,
      pollIntervalMs: 1_000,
    });
    const updates: GovernedMutationRecord[] = [];

    const tracking = tracker.track(seedRecord(), (record) => {
      updates.push(record);
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(1_000);
    await tracking;

    expect(
      transport.calls.filter(({ name }) => name === "GetApproval"),
    ).toHaveLength(2);
    expect(
      transport.calls.filter(
        ({ name }) => name === "GetExecutionReceipt",
      ),
    ).toHaveLength(2);
    expect(updates.at(-1)).toMatchObject({
      state: "succeeded",
      evidenceStatus: "unverifiable",
      operationId: "operation-synthetic-001",
      approval: null,
      receipt: null,
    });

    transport.operationStatuses = ["completed"];
    transport.approvalAvailable = true;
    transport.receiptAvailable = true;
    await tracker.refresh(updates.at(-1)!, (record) => {
      updates.push(record);
    });
    expect(updates.at(-1)).toMatchObject({
      state: "succeeded",
      evidenceStatus: "complete",
      operationId: "operation-synthetic-001",
      approval: {
        approvalId: "approval-synthetic-001",
      },
      receipt: {
        operationId: "operation-synthetic-001",
      },
    });
  });

  test("outreach approval tracking waits for a late exact approval contract before resolving terminal evidence", async () => {
    vi.useFakeTimers();
    const transport = new TrackerTransport();
    transport.operationStatuses = ["completed", "completed"];
    transport.operationResults = [
      { outreach_id: "outreach-synthetic-001" },
      {
        outreach_id: "outreach-synthetic-001",
        approval_contract_id: "approval-synthetic-001",
      },
    ];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 2,
      pollIntervalMs: 1_000,
    });
    const updates: GovernedMutationRecord[] = [];
    const record: GovernedMutationRecord = {
      ...seedRecord(),
      commandName: "outreach.approve",
      approvalContractId: null,
    };

    const tracking = tracker.track(record, (updatedRecord) => {
      updates.push(updatedRecord);
    });
    await vi.advanceTimersByTimeAsync(0);

    expect(vi.getTimerCount()).toBe(1);
    expect(
      transport.calls.filter(({ name }) => name === "GetApproval"),
    ).toHaveLength(0);

    await vi.advanceTimersByTimeAsync(1_000);
    await tracking;

    expect(
      transport.calls.filter(({ name }) => name === "GetOperation"),
    ).toHaveLength(2);
    expect(
      transport.calls.filter(({ name }) => name === "GetApproval"),
    ).toEqual([
      {
        name: "GetApproval",
        variables: { id: "approval-synthetic-001" },
      },
    ]);
    expect(updates.at(-1)).toMatchObject({
      state: "succeeded",
      operationId: "operation-synthetic-001",
      approvalContractId: "approval-synthetic-001",
      approval: {
        approvalId: "approval-synthetic-001",
      },
    });
  });

  test("pending approval without a contract ID exhausts bounded polling and remains exactly refreshable by operation ID", async () => {
    vi.useFakeTimers();
    const transport = new TrackerTransport();
    transport.operationStatuses = ["completed", "completed"];
    transport.operationResults = [
      { status: "pending_approval" },
      { status: "pending_approval" },
    ];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 2,
      pollIntervalMs: 1_000,
    });
    const updates: GovernedMutationRecord[] = [];
    const record: GovernedMutationRecord = {
      ...seedRecord(),
      approvalContractId: null,
    };

    const tracking = tracker.track(record, (updatedRecord) => {
      updates.push(updatedRecord);
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(1_000);
    await tracking;

    expect(
      transport.calls.filter(({ name }) => name === "GetOperation"),
    ).toHaveLength(2);
    expect(updates.at(-1)).toMatchObject({
      state: "approval-required",
      evidenceStatus: "unverifiable",
      operationId: "operation-synthetic-001",
      approvalContractId: null,
      approval: null,
      localReason:
        "Polling ended before complete terminal operation evidence was available. The operation ID is preserved for manual refresh.",
    });

    transport.operationStatuses = ["completed"];
    transport.operationResults = [
      {
        status: "pending_approval",
        approval_contract_id: "approval-synthetic-001",
      },
    ];
    await tracker.refresh(updates.at(-1)!, (updatedRecord) => {
      updates.push(updatedRecord);
    });

    expect(updates.at(-1)).toMatchObject({
      state: "approval-required",
      evidenceStatus: "complete",
      operationId: "operation-synthetic-001",
      approvalContractId: "approval-synthetic-001",
      approval: {
        approvalId: "approval-synthetic-001",
      },
    });
  });

  test("refresh preserves refused handle reason and code when terminal evidence has no newer reason", async () => {
    const transport = new TrackerTransport();
    transport.operationStatuses = ["completed"];
    transport.operationErrors = [null];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 1,
      pollIntervalMs: 1,
    });
    const updates: GovernedMutationRecord[] = [];
    const refusedRecord: GovernedMutationRecord = {
      ...seedRecord(),
      state: "refused",
      serverReasonCode: "synthetic_policy_denied",
      serverReason: "Synthetic policy did not authorize this operation",
      approvalContractId: null,
    };

    await tracker.refresh(refusedRecord, (record) => {
      updates.push(record);
    });

    expect(updates.at(-1)).toMatchObject({
      operationId: "operation-synthetic-001",
      serverReasonCode: "synthetic_policy_denied",
      serverReason:
        "Synthetic policy did not authorize this operation",
    });
  });

  test("a refused terminal outcome survives an evidence read failure and later manual recovery", async () => {
    const transport = new TrackerTransport();
    transport.operationStatuses = ["refused"];
    transport.failExecutionReceiptRead = true;
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 1,
      pollIntervalMs: 1,
    });
    const updates: GovernedMutationRecord[] = [];

    await tracker.track(seedRecord(), (record) => {
      updates.push(record);
    });

    expect(updates.at(-1)).toMatchObject({
      state: "refused",
      evidenceStatus: "unverifiable",
      operationId: "operation-synthetic-001",
      serverReason: "synthetic_policy_denied",
    });
    expect(JSON.stringify(updates)).not.toContain("tracker-secret");

    transport.operationStatuses = ["refused"];
    transport.failExecutionReceiptRead = false;
    await tracker.refresh(updates.at(-1)!, (record) => {
      updates.push(record);
    });

    expect(updates.at(-1)).toMatchObject({
      state: "refused",
      evidenceStatus: "complete",
      operationId: "operation-synthetic-001",
    });
  });

  test("a failed terminal outcome survives exhausted missing evidence and later manual recovery", async () => {
    vi.useFakeTimers();
    const transport = new TrackerTransport();
    transport.operationStatuses = ["failed", "failed"];
    transport.receiptAvailable = false;
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 2,
      pollIntervalMs: 1_000,
    });
    const updates: GovernedMutationRecord[] = [];

    const tracking = tracker.track(seedRecord(), (record) => {
      updates.push(record);
    });
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(1_000);
    await tracking;

    expect(updates.at(-1)).toMatchObject({
      state: "failed",
      evidenceStatus: "unverifiable",
      operationId: "operation-synthetic-001",
      receipt: null,
    });

    transport.operationStatuses = ["failed"];
    transport.receiptAvailable = true;
    await tracker.refresh(updates.at(-1)!, (record) => {
      updates.push(record);
    });

    expect(updates.at(-1)).toMatchObject({
      state: "failed",
      evidenceStatus: "complete",
      operationId: "operation-synthetic-001",
    });
  });

  test.each(["pending", "running"] as const)(
    "emits the distinct %s operation state before bounded polling continues",
    async (status) => {
      vi.useFakeTimers();
      const transport = new TrackerTransport();
      transport.operationStatuses = [status, status];
      const tracker = new OperationTracker(createTrackerClient(transport), {
        maxPollAttempts: 2,
        pollIntervalMs: 1_000,
      });
      const updates: GovernedMutationRecord[] = [];

      const tracking = tracker.track(seedRecord(), (record) => {
        updates.push(record);
      });
      await vi.advanceTimersByTimeAsync(0);

      expect(updates[0]?.state).toBe(status);
      expect(updates[0]?.evidenceStatus).toBe("pending");
      tracker.stopAll();
      await tracking;
    },
  );

  test("stopping during an in-flight operation read prevents all subsequent reads and updates", async () => {
    const transport = new GatedTrackerTransport();
    transport.operationStatuses = ["running"];
    const tracker = new OperationTracker(createTrackerClient(transport), {
      maxPollAttempts: 3,
      pollIntervalMs: 1,
    });
    const updates: GovernedMutationRecord[] = [];

    const tracking = tracker.track(seedRecord(), (record) => {
      updates.push(record);
    });
    await Promise.resolve();
    tracker.stopAll();
    transport.release?.();
    await tracking;

    expect(transport.calls.map(({ name }) => name)).toEqual([
      "GetOperation",
    ]);
    expect(updates).toEqual([]);
  });
});
