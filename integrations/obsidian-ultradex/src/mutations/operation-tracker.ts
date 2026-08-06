import type {
  ApprovalEvidence,
  ExecutionReceiptEvidence,
  JobSearchCommandName,
  Operation,
  OperationLifecycleEvent,
  UltradexReadClient,
} from "@ultradex/sdk";

export type GovernedOutcomeState =
  | "accepted"
  | "pending"
  | "running"
  | "approval-required"
  | "refused"
  | "failed"
  | "succeeded"
  | "unverifiable";

export type EvidenceStatus =
  | "pending"
  | "complete"
  | "unverifiable";

export interface GovernedMutationRecord {
  readonly id: string;
  readonly commandName: JobSearchCommandName;
  readonly consequence: string;
  readonly submittedAt: string;
  readonly idempotencyKey: string;
  readonly correlationId: string;
  readonly contractId: string | null;
  readonly operationId: string | null;
  readonly state: GovernedOutcomeState;
  readonly evidenceStatus: EvidenceStatus;
  readonly serverReasonCode: string | null;
  readonly serverReason: string | null;
  readonly localReason: string | null;
  readonly completionUnknown: boolean;
  readonly resubmissionBlocked: boolean;
  readonly events: readonly OperationLifecycleEvent[];
  readonly approvalContractId: string | null;
  readonly approval: ApprovalEvidence | null;
  readonly receipt: ExecutionReceiptEvidence | null;
  readonly localSignatureVerification: "unavailable";
}

export interface OperationTrackerOptions {
  readonly maxPollAttempts?: number;
  readonly pollIntervalMs?: number;
}

export type OperationClientProvider =
  | UltradexReadClient
  | (() => UltradexReadClient);

const TERMINAL_OPERATION_STATES = new Set([
  "completed",
  "failed",
  "refused",
]);
const KNOWN_TERMINAL_OUTCOMES = new Set<GovernedOutcomeState>([
  "approval-required",
  "refused",
  "failed",
  "succeeded",
]);

function objectString(value: unknown, key: string): string | null {
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value)
  ) {
    return null;
  }
  const candidate = (value as Readonly<Record<string, unknown>>)[key];
  return typeof candidate === "string" && candidate.length > 0
    ? candidate
    : null;
}

function operationState(
  operation: Operation,
  receipt: ExecutionReceiptEvidence | null,
): GovernedOutcomeState {
  if (receipt?.status === "refused" || operation.status === "refused") {
    return "refused";
  }
  if (receipt?.status === "failed" || operation.status === "failed") {
    return "failed";
  }
  if (
    operation.status === "completed" &&
    objectString(operation.result, "status") === "pending_approval"
  ) {
    return "approval-required";
  }
  if (operation.status === "completed") {
    return "succeeded";
  }
  return operation.status;
}

function unverifiableReadFailure(
  record: GovernedMutationRecord,
  localReason =
    "Operation evidence could not be refreshed. The operation ID is preserved for a later manual refresh.",
): GovernedMutationRecord {
  return {
    ...record,
    state: KNOWN_TERMINAL_OUTCOMES.has(record.state)
      ? record.state
      : "unverifiable",
    evidenceStatus: "unverifiable",
    localReason,
  };
}

interface ActiveTracking {
  cancelled: boolean;
  timer: ReturnType<typeof globalThis.setTimeout> | null;
  releaseWait: (() => void) | null;
  promise: Promise<void>;
}

export class OperationTracker {
  private readonly maxPollAttempts: number;
  private readonly pollIntervalMs: number;
  private readonly active = new Map<string, ActiveTracking>();
  private stopped = false;

  constructor(
    private readonly clientProvider: OperationClientProvider,
    options: OperationTrackerOptions = {},
  ) {
    this.maxPollAttempts = options.maxPollAttempts ?? 5;
    this.pollIntervalMs = options.pollIntervalMs ?? 1_000;
  }

  track(
    initialRecord: GovernedMutationRecord,
    onUpdate: (record: GovernedMutationRecord) => void,
  ): Promise<void> {
    return this.start(
      initialRecord,
      onUpdate,
      this.maxPollAttempts,
      true,
    );
  }

  refresh(
    record: GovernedMutationRecord,
    onUpdate: (record: GovernedMutationRecord) => void,
  ): Promise<void> {
    return this.start(record, onUpdate, 1, false);
  }

  private start(
    initialRecord: GovernedMutationRecord,
    onUpdate: (record: GovernedMutationRecord) => void,
    maxAttempts: number,
    markNonTerminalUnavailable: boolean,
  ): Promise<void> {
    if (this.stopped || initialRecord.operationId === null) {
      return Promise.resolve();
    }
    const operationId = initialRecord.operationId;
    const existing = this.active.get(operationId);
    if (existing !== undefined) {
      return existing.promise;
    }
    const session: ActiveTracking = {
      cancelled: false,
      timer: null,
      releaseWait: null,
      promise: Promise.resolve(),
    };
    session.promise = this.runTracking(
      initialRecord,
      onUpdate,
      session,
      maxAttempts,
      markNonTerminalUnavailable,
    );
    this.active.set(operationId, session);
    void session.promise.finally(() => {
      if (this.active.get(operationId) === session) {
        this.active.delete(operationId);
      }
    });
    return session.promise;
  }

  stopAll(): void {
    this.stopped = true;
    for (const session of this.active.values()) {
      session.cancelled = true;
      if (session.timer !== null) {
        globalThis.clearTimeout(session.timer);
        session.timer = null;
      }
      session.releaseWait?.();
      session.releaseWait = null;
    }
  }

  private async runTracking(
    initialRecord: GovernedMutationRecord,
    onUpdate: (record: GovernedMutationRecord) => void,
    session: ActiveTracking,
    maxAttempts: number,
    markNonTerminalUnavailable: boolean,
  ): Promise<void> {
    let record = initialRecord;
    let incompleteTerminalEvidence = false;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      let poll:
        | Exclude<
            Awaited<ReturnType<OperationTracker["pollOnce"]>>,
            null
          >
        | null;
      try {
        poll = await this.pollOnce(record, session);
      } catch {
        if (!this.stopped && !session.cancelled) {
          onUpdate(unverifiableReadFailure(record));
        }
        return;
      }
      if (poll === null || this.stopped || session.cancelled) {
        return;
      }
      record = poll.record;
      incompleteTerminalEvidence = poll.incompleteTerminalEvidence;
      onUpdate(record);
      if (poll.terminal) {
        return;
      }
      if (attempt + 1 < maxAttempts) {
        await this.waitForNextPoll(session);
        if (this.stopped || session.cancelled) {
          return;
        }
      }
    }
    if (
      !this.stopped &&
      !session.cancelled &&
      (markNonTerminalUnavailable || incompleteTerminalEvidence)
    ) {
      onUpdate(
        unverifiableReadFailure(
          record,
          "Polling ended before complete terminal operation evidence was available. The operation ID is preserved for manual refresh.",
        ),
      );
    }
  }

  private waitForNextPoll(session: ActiveTracking): Promise<void> {
    return new Promise((resolve) => {
      const release = (): void => {
        session.timer = null;
        session.releaseWait = null;
        resolve();
      };
      session.releaseWait = release;
      session.timer = globalThis.setTimeout(
        release,
        this.pollIntervalMs,
      );
    });
  }

  private async pollOnce(
    record: GovernedMutationRecord,
    session: ActiveTracking,
  ): Promise<{
    readonly record: GovernedMutationRecord;
    readonly terminal: boolean;
    readonly incompleteTerminalEvidence: boolean;
  } | null> {
    const operationId = record.operationId;
    if (
      operationId === null ||
      this.stopped ||
      session.cancelled
    ) {
      return null;
    }
    const client =
      typeof this.clientProvider === "function"
        ? this.clientProvider()
        : this.clientProvider;
    const operation = await client.getOperation(operationId);
    if (this.stopped || session.cancelled) {
      return null;
    }
    if (operation === null) {
      try {
        const events = await client.getOperationEvents(operationId);
        if (this.stopped || session.cancelled) {
          return null;
        }
        return {
          record: {
            ...record,
            evidenceStatus: "pending",
            localReason: null,
            events,
          },
          terminal: false,
          incompleteTerminalEvidence: false,
        };
      } catch {
        return {
          record: unverifiableReadFailure(record),
          terminal: true,
          incompleteTerminalEvidence: false,
        };
      }
    }
    const terminalOperation = TERMINAL_OPERATION_STATES.has(
      operation.status,
    );
    const resolvedRecord: GovernedMutationRecord = {
      ...record,
      state: operationState(operation, record.receipt),
      evidenceStatus: "pending",
      serverReason: operation.error ?? record.serverReason,
      localReason: null,
    };
    const approvalContractId =
      record.approvalContractId ??
      objectString(operation.result, "approval_contract_id");
    const approvalEvidenceRequired =
      record.commandName === "outreach.approve" ||
      objectString(operation.result, "status") ===
        "pending_approval";
    try {
      const events = await client.getOperationEvents(operationId);
      if (this.stopped || session.cancelled) {
        return null;
      }
      const approval =
        terminalOperation && approvalContractId !== null
          ? await client.getApproval(approvalContractId)
          : record.approval;
      if (this.stopped || session.cancelled) {
        return null;
      }
      const receipt = terminalOperation
        ? await client.getExecutionReceipt(operationId)
        : record.receipt;
      if (this.stopped || session.cancelled) {
        return null;
      }
      const terminalEvidenceComplete =
        terminalOperation &&
        receipt !== null &&
        (approvalContractId === null
          ? !approvalEvidenceRequired
          : approval !== null);
      return {
        record: {
          ...resolvedRecord,
          state: operationState(operation, receipt),
          evidenceStatus: terminalEvidenceComplete
            ? "complete"
            : "pending",
          serverReasonCode:
            receipt?.reasonCode ?? record.serverReasonCode,
          events,
          approvalContractId,
          approval,
          receipt,
        },
        terminal: terminalEvidenceComplete,
        incompleteTerminalEvidence:
          terminalOperation && !terminalEvidenceComplete,
      };
    } catch {
      return {
        record: unverifiableReadFailure(resolvedRecord),
        terminal: true,
        incompleteTerminalEvidence: false,
      };
    }
  }
}
