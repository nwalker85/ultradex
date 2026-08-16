import type {
  ContractHandle,
  ExecutionReceiptEvidence,
  Operation,
  UltradexReadClient,
} from "@ultradex/sdk";

import {
  contractStatusTone,
  isTerminalOperationStatus,
  nextPollDelayMs,
  operationTone,
  type Tone,
} from "./governed-write.js";

export type TrackerPhase = "polling" | "terminal";

type TrackerClient = Pick<UltradexReadClient, "getOperation" | "getExecutionReceipt">;

/**
 * Tier 2 of the governed-write pattern (PRD section 8.2). One instance per
 * operationId, held in the module-level registry below so it is page-scoped
 * (FR-GW-7: survives a component unmounting on navigation) and deduped
 * (NFR-2: two components tracking the same operationId share one poll loop).
 */
export class OperationTrackerState {
  readonly operationId: string;
  operation = $state<Operation | null>(null);
  receipt = $state<ExecutionReceiptEvidence | null>(null);
  pollError = $state<unknown>(null);
  receiptError = $state<unknown>(null);
  phase = $state<TrackerPhase>("polling");
  /** Tone available before `operation` has loaded (derived from the Tier 1 handle). */
  knownTone = $state<Tone | null>(null);

  private readonly client: TrackerClient;
  private attempt = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private started = false;
  private resolved = false;

  constructor(client: TrackerClient, operationId: string) {
    this.client = client;
    this.operationId = operationId;
  }

  /** Begin polling `getOperation` at 1.5s with capped backoff until terminal (FR-GW-7). */
  start(): void {
    if (this.started || this.resolved) {
      return;
    }
    this.started = true;
    void this.poll();
  }

  /**
   * FR-GW-2 — the write already resolved synchronously (e.g. the 503
   * dispatch-failure path, already terminal-failed server-side). Do not
   * start a polling loop; fetch the operation and receipt exactly once for
   * full detail.
   */
  markKnownTerminal(handle: ContractHandle): void {
    if (this.resolved) {
      return;
    }
    this.started = true;
    this.resolved = true;
    this.knownTone = contractStatusTone(handle.status);
    this.phase = "terminal";
    void this.fetchOnce();
  }

  /** Current tone, preferring the live Operation once loaded over the Tier 1 handle's status. */
  get tone(): Tone {
    if (this.operation !== null) {
      return operationTone(this.operation.status);
    }
    return this.knownTone ?? "neutral";
  }

  dispose(): void {
    if (this.timer !== undefined) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
  }

  private async fetchOnce(): Promise<void> {
    try {
      this.operation = await this.client.getOperation(this.operationId);
    } catch (error) {
      this.pollError = error;
    }
    void this.loadReceipt();
  }

  private async poll(): Promise<void> {
    if (this.resolved) {
      return;
    }
    try {
      const operation = await this.client.getOperation(this.operationId);
      if (this.resolved) {
        return;
      }
      this.operation = operation;
      this.pollError = null;
      if (operation !== null && isTerminalOperationStatus(operation.status)) {
        this.resolved = true;
        this.phase = "terminal";
        void this.loadReceipt();
        return;
      }
    } catch (error) {
      if (this.resolved) {
        return;
      }
      // A transient read failure mid-poll is not FR-GW-5's "unclear whether
      // the write was received" — the write already happened (we hold its
      // operationId); this is a read retrying, not a resubmission.
      this.pollError = error;
    }
    if (this.resolved) {
      return;
    }
    const delay = nextPollDelayMs(this.attempt);
    this.attempt += 1;
    this.timer = setTimeout(() => void this.poll(), delay);
  }

  private async loadReceipt(): Promise<void> {
    // FR-GW-8 — fetched for all three terminal outcomes, including `refused`.
    try {
      this.receipt = await this.client.getExecutionReceipt(this.operationId);
    } catch (error) {
      this.receiptError = error;
    }
  }
}

const registry = new Map<string, OperationTrackerState>();

export function getOperationTracker(
  client: TrackerClient,
  operationId: string,
): OperationTrackerState {
  const existing = registry.get(operationId);
  if (existing !== undefined) {
    return existing;
  }
  const created = new OperationTrackerState(client, operationId);
  registry.set(operationId, created);
  return created;
}

/** Test-only escape hatch — production code never needs to clear the registry. */
export function __resetOperationTrackerRegistryForTests(): void {
  registry.forEach((tracker) => tracker.dispose());
  registry.clear();
}
