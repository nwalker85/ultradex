import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ContractHandle, ExecutionReceiptEvidence, Operation } from "@ultradex/sdk";

import {
  __resetOperationTrackerRegistryForTests,
  getOperationTracker,
  OperationTrackerState,
} from "./operation-tracker.svelte.js";
import { POLL_BASE_MS } from "./governed-write.js";

function operation(overrides: Partial<Operation> & { status: Operation["status"] }): Operation {
  return {
    id: "operation-1",
    correlationId: null,
    command: "opportunities.create",
    createdAt: "2026-08-08T00:00:00Z",
    startedAt: null,
    completedAt: null,
    result: null,
    error: null,
    freshness: null,
    ...overrides,
  } as Operation;
}

function receipt(overrides: Partial<ExecutionReceiptEvidence> = {}): ExecutionReceiptEvidence {
  return {
    receiptId: "opaque:v1:receipt",
    operationId: "operation-1",
    eventId: "opaque:v1:event",
    status: "succeeded",
    reasonCode: null,
    payload: {} as ExecutionReceiptEvidence["payload"],
    receiptHash: `sha256:${"a".repeat(64)}`,
    createdAt: "2026-08-08T00:00:01Z",
    completedAt: "2026-08-08T00:00:01Z",
    proofStatus: "server-recorded",
    ...overrides,
  } as ExecutionReceiptEvidence;
}

function handle(overrides: Partial<ContractHandle> & { status: ContractHandle["status"] }): ContractHandle {
  return {
    contractId: "contract-1",
    operationId: "operation-1",
    submittedAt: "2026-08-08T00:00:00Z",
    correlationId: "correlation-1",
    ...overrides,
  } as ContractHandle;
}

describe("OperationTrackerState", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    __resetOperationTrackerRegistryForTests();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("start() polls once immediately and stays in 'polling' phase while pending", async () => {
    const getOperation = vi.fn().mockResolvedValue(operation({ status: "pending" }));
    const getExecutionReceipt = vi.fn();
    const tracker = new OperationTrackerState({ getOperation, getExecutionReceipt }, "operation-1");

    tracker.start();
    await vi.waitFor(() => expect(getOperation).toHaveBeenCalledTimes(1));

    expect(tracker.phase).toBe("polling");
    expect(tracker.operation?.status).toBe("pending");
  });

  it("FR-GW-7: schedules the next poll at the 1.5s base delay", async () => {
    const getOperation = vi.fn().mockResolvedValue(operation({ status: "pending" }));
    const getExecutionReceipt = vi.fn();
    const tracker = new OperationTrackerState({ getOperation, getExecutionReceipt }, "operation-1");

    tracker.start();
    await vi.waitFor(() => expect(getOperation).toHaveBeenCalledTimes(1));

    await vi.advanceTimersByTimeAsync(POLL_BASE_MS - 10);
    expect(getOperation).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(20);
    await vi.waitFor(() => expect(getOperation).toHaveBeenCalledTimes(2));
  });

  it("transitions to 'terminal' and fetches the receipt once the operation is terminal (FR-GW-8)", async () => {
    const getOperation = vi.fn().mockResolvedValue(operation({ status: "completed", completedAt: "2026-08-08T00:00:02Z" }));
    const getExecutionReceipt = vi.fn().mockResolvedValue(receipt());
    const tracker = new OperationTrackerState({ getOperation, getExecutionReceipt }, "operation-1");

    tracker.start();
    await vi.waitFor(() => expect(tracker.phase).toBe("terminal"));
    await vi.waitFor(() => expect(tracker.receipt).not.toBeNull());

    expect(getExecutionReceipt).toHaveBeenCalledExactlyOnceWith("operation-1");
    expect(tracker.tone).toBe("success");
  });

  it("FR-GW-8: fetches the receipt for a 'refused' terminal outcome too", async () => {
    const getOperation = vi
      .fn()
      .mockResolvedValue(operation({ status: "refused", completedAt: "2026-08-08T00:00:02Z", error: "scorer_unbound" }));
    const getExecutionReceipt = vi.fn().mockResolvedValue(receipt({ status: "refused", reasonCode: "safety_refusal" }));
    const tracker = new OperationTrackerState({ getOperation, getExecutionReceipt }, "operation-1");

    tracker.start();
    await vi.waitFor(() => expect(tracker.phase).toBe("terminal"));
    await vi.waitFor(() => expect(tracker.receipt).not.toBeNull());

    expect(getExecutionReceipt).toHaveBeenCalledTimes(1);
    // FR-OPS-3: refused is warning, never danger.
    expect(tracker.tone).toBe("warning");
  });

  it("FR-GW-2: markKnownTerminal never polls — getOperation is called exactly once, no timer scheduled", async () => {
    const getOperation = vi.fn().mockResolvedValue(operation({ status: "failed", completedAt: "2026-08-08T00:00:02Z" }));
    const getExecutionReceipt = vi.fn().mockResolvedValue(receipt({ status: "failed", reasonCode: "executor_failure" }));
    const tracker = new OperationTrackerState({ getOperation, getExecutionReceipt }, "operation-1");

    tracker.markKnownTerminal(handle({ status: "failed" }));

    // Immediately terminal — no need to wait out a 1.5s poll interval.
    expect(tracker.phase).toBe("terminal");
    expect(tracker.tone).toBe("danger");

    await vi.waitFor(() => expect(tracker.operation?.status).toBe("failed"));
    await vi.waitFor(() => expect(tracker.receipt).not.toBeNull());

    // Advancing time well past several poll intervals must not trigger a second call.
    await vi.advanceTimersByTimeAsync(10_000);
    expect(getOperation).toHaveBeenCalledTimes(1);
  });

  it("getOperationTracker dedupes by operationId (NFR-2: no two independent poll loops)", () => {
    const getOperation = vi.fn().mockResolvedValue(operation({ status: "pending" }));
    const getExecutionReceipt = vi.fn();
    const client = { getOperation, getExecutionReceipt };

    const first = getOperationTracker(client, "operation-1");
    const second = getOperationTracker(client, "operation-1");
    const third = getOperationTracker(client, "operation-2");

    expect(first).toBe(second);
    expect(first).not.toBe(third);
  });

  it("start() is idempotent — calling it again does not begin a second poll loop", async () => {
    const getOperation = vi.fn().mockResolvedValue(operation({ status: "pending" }));
    const getExecutionReceipt = vi.fn();
    const tracker = new OperationTrackerState({ getOperation, getExecutionReceipt }, "operation-1");

    tracker.start();
    tracker.start();
    tracker.start();
    await vi.waitFor(() => expect(getOperation).toHaveBeenCalledTimes(1));

    await vi.advanceTimersByTimeAsync(50);
    expect(getOperation).toHaveBeenCalledTimes(1);
  });
});
