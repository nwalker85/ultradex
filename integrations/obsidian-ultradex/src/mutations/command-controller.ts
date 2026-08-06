import type {
  ContractHandle,
  JobSearchCommand,
  UltradexCommandClient,
} from "@ultradex/sdk";
import { UltradexTimeoutError } from "@ultradex/sdk";

import type { ProjectionStore } from "../projection-store.js";
import {
  type CommandCustodyJournal,
  type CommandCustodyJournalEntry,
} from "./command-custody-journal.js";
import {
  CommandReviewError,
  commandFormMetadata,
} from "./command-forms.js";
import {
  type GovernedMutationRecord,
  type GovernedOutcomeState,
  OperationTracker,
} from "./operation-tracker.js";

export type GeneratedCommandIdKind = "idempotency" | "correlation";
export type CommandClientProvider =
  | UltradexCommandClient
  | (() => UltradexCommandClient);

export interface CommandControllerOptions {
  readonly client: CommandClientProvider;
  readonly projectionStore: ProjectionStore;
  readonly operationTracker?: OperationTracker;
  readonly journal?: CommandCustodyJournal;
  readonly createId?: (kind: GeneratedCommandIdKind) => string;
  readonly now?: () => Date;
}

export interface CommandConfirmation {
  readonly id: string;
  readonly command: JobSearchCommand;
  readonly idempotencyKey: string;
  readonly correlationId: string;
  readonly preparedAt: string;
  readonly label: string;
  readonly consequence: string;
  readonly boundFields: readonly CommandBoundField[];
  readonly outreachApprovalBinding: OutreachApprovalBinding | null;
  readonly bindingError: string | null;
  readonly stage:
    | "awaiting-confirmation"
    | "awaiting-second-confirmation"
    | "submitting";
}

export interface CommandBoundField {
  readonly label: string;
  readonly value: string;
}

export interface OutreachApprovalBinding {
  readonly outreachId: string;
  readonly messageCommitment: string;
  readonly channel: "gmail" | "linkedin" | "manual";
}

export interface CommandControllerState {
  readonly confirmation: CommandConfirmation | null;
  readonly records: readonly GovernedMutationRecord[];
  readonly refreshingRecordIds: readonly string[];
}

export type CommandControllerListener = (
  state: CommandControllerState,
) => void;

type CommandOptions = {
  readonly idempotencyKey: string;
  readonly correlationId: string;
};

function submitCommand(
  client: UltradexCommandClient,
  command: JobSearchCommand,
  options: CommandOptions,
): Promise<ContractHandle> {
  switch (command.commandName) {
    case "sources.ingest":
      return client.submitSourcesIngest(command.parameters, options);
    case "opportunities.create":
      return client.submitOpportunityCreate(command.parameters, options);
    case "opportunities.score":
      return client.submitOpportunityScore(command.parameters, options);
    case "applications.transition":
      return client.submitApplicationTransition(command.parameters, options);
    case "relationships.sync":
      return client.submitRelationshipSync(command.parameters, options);
    case "outreach.prepare":
      return client.submitOutreachPrepare(command.parameters, options);
    case "outreach.approve":
      return client.submitOutreachApprove(command.parameters, options);
    case "outreach.send":
      return client.submitOutreachSend(command.parameters, options);
    case "evidence.export":
      return client.submitEvidenceExport(command.parameters, options);
  }
}

function defaultCreateId(kind: GeneratedCommandIdKind): string {
  const value = globalThis.crypto.randomUUID();
  return `obsidian-${kind}-${value}`;
}

export function isMutationAvailable(store: ProjectionStore): boolean {
  const state = store.getState();
  return (
    state.status === "ready" &&
    state.errorCategory === null &&
    state.snapshot !== null &&
    state.snapshot.aggregateFreshness.status === "fresh"
  );
}

function handleState(handle: ContractHandle): GovernedOutcomeState {
  switch (handle.status) {
    case "refused":
      return "refused";
    case "failed":
    case "cancelled":
    case "expired":
    case "revoked":
      return "failed";
    case "succeeded":
      return "succeeded";
    case "unverifiable":
      return "unverifiable";
    case "pending":
      return "pending";
    case "running":
      return "running";
    default:
      return "accepted";
  }
}

function restoredRecord(
  entry: CommandCustodyJournalEntry,
): GovernedMutationRecord {
  const interruptedSubmission = entry.state === "submitting";
  const completionUnknown =
    entry.operationId === null &&
    (interruptedSubmission || entry.state === "unverifiable");
  return {
    id: entry.idempotencyKey,
    commandName: entry.commandName,
    consequence: commandFormMetadata(entry.commandName).consequence,
    submittedAt: entry.submittedAt,
    idempotencyKey: entry.idempotencyKey,
    correlationId: entry.correlationId,
    contractId: entry.contractId,
    operationId: entry.operationId,
    state: interruptedSubmission ? "unverifiable" : entry.state,
    evidenceStatus:
      entry.operationId === null ? "unverifiable" : "pending",
    serverReasonCode: null,
    serverReason: null,
    localReason: completionUnknown
      ? "Completion unknown after restart. This submitted attempt cannot be resubmitted."
      : null,
    completionUnknown,
    resubmissionBlocked: true,
    events: [],
    approvalContractId: entry.approvalContractId,
    approval: null,
    receipt: null,
    localSignatureVerification: "unavailable",
  };
}

function custodyUnavailableRecord(
  record: GovernedMutationRecord,
): GovernedMutationRecord {
  return {
    ...record,
    state: "unverifiable",
    evidenceStatus: "unverifiable",
    localReason:
      "Durable command custody could not be updated. Any known operation identifiers are retained in memory, and this attempt cannot be resubmitted.",
    completionUnknown: true,
    resubmissionBlocked: true,
  };
}

function commandBoundFields(
  command: JobSearchCommand,
  outreachApprovalBinding: OutreachApprovalBinding | null,
): readonly CommandBoundField[] {
  switch (command.commandName) {
    case "sources.ingest":
      return [
        { label: "Source kind", value: command.parameters.sourceKind },
        {
          label: "Opaque source reference",
          value: command.parameters.sourceRef,
        },
        { label: "Observed at", value: command.parameters.observedAt },
      ];
    case "opportunities.create":
      return [
        { label: "Employer", value: command.parameters.employer },
        { label: "Role title", value: command.parameters.title },
        {
          label: "Source evidence ID",
          value: command.parameters.sourceEvidenceId,
        },
      ];
    case "opportunities.score":
      return [
        {
          label: "Opportunity ID",
          value: command.parameters.opportunityId,
        },
        { label: "Scoring lens", value: command.parameters.lens },
      ];
    case "applications.transition":
      return [
        {
          label: "Application ID",
          value: command.parameters.applicationId,
        },
        { label: "New state", value: command.parameters.status },
        { label: "Occurred at", value: command.parameters.occurredAt },
      ];
    case "relationships.sync":
      return [
        {
          label: "Opportunity ID",
          value: command.parameters.opportunityId,
        },
        {
          label: "Opaque Dex contact reference",
          value: command.parameters.dexContactRef,
        },
      ];
    case "outreach.prepare":
      return [
        {
          label: "Opportunity ID",
          value: command.parameters.opportunityId,
        },
        { label: "Channel", value: command.parameters.channel },
        {
          label: "Message commitment",
          value: command.parameters.messageCommitment,
        },
        {
          label: "Relationship ID",
          value: command.parameters.relationshipId ?? "Not provided",
        },
      ];
    case "outreach.approve": {
      return [
        {
          label: "Outreach ID",
          value: command.parameters.outreachId,
        },
        {
          label: "Message commitment",
          value: command.parameters.messageCommitment,
        },
        {
          label: "Channel",
          value:
            outreachApprovalBinding?.channel ??
            "Unavailable in verified projection",
        },
      ];
    }
    case "outreach.send":
      return [
        {
          label: "Outreach ID",
          value: command.parameters.outreachId,
        },
        {
          label: "Exact approval contract ID",
          value: command.parameters.approvalContractId,
        },
        {
          label: "Message commitment",
          value: command.parameters.messageCommitment,
        },
        { label: "Channel", value: command.parameters.channel },
      ];
    case "evidence.export":
      return [
        {
          label: "Subject type",
          value: command.parameters.subjectType,
        },
        {
          label: "Subject ID",
          value: command.parameters.subjectId,
        },
        {
          label: "Export profile",
          value: command.parameters.profile,
        },
      ];
  }
}

function outreachApprovalBinding(
  command: JobSearchCommand,
  store: ProjectionStore,
): OutreachApprovalBinding | null {
  if (command.commandName !== "outreach.approve") {
    return null;
  }
  const item = store
    .getState()
    .snapshot?.outreach.items.find(
      (candidate) =>
        candidate.outreachId === command.parameters.outreachId,
    );
  if (item === undefined) {
    throw new CommandReviewError(
      "Refresh projections and review an outreach item that is awaiting approval.",
    );
  }
  if (
    item.status !== "pending_approval" ||
    item.messageCommitment !== command.parameters.messageCommitment
  ) {
    throw new CommandReviewError(
      "The verified outreach binding does not match this approval request. Refresh projections and review it again.",
    );
  }
  return {
    outreachId: item.outreachId,
    messageCommitment: item.messageCommitment,
    channel: item.channel,
  };
}

function sameOutreachApprovalBinding(
  left: OutreachApprovalBinding | null,
  right: OutreachApprovalBinding | null,
): boolean {
  return (
    left !== null &&
    right !== null &&
    left.outreachId === right.outreachId &&
    left.messageCommitment === right.messageCommitment &&
    left.channel === right.channel
  );
}

export class CommandController {
  private readonly clientProvider: CommandClientProvider;
  private readonly projectionStore: ProjectionStore;
  private readonly operationTracker: OperationTracker | undefined;
  private readonly journal: CommandCustodyJournal | undefined;
  private readonly createId: (
    kind: GeneratedCommandIdKind,
  ) => string;
  private readonly now: () => Date;
  private confirmation: CommandConfirmation | null = null;
  private records: readonly GovernedMutationRecord[];
  private readonly listeners = new Set<CommandControllerListener>();
  private readonly refreshingRecordIds = new Set<string>();
  private stopped = false;

  constructor(options: CommandControllerOptions) {
    this.clientProvider = options.client;
    this.projectionStore = options.projectionStore;
    this.operationTracker = options.operationTracker;
    this.journal = options.journal;
    this.createId = options.createId ?? defaultCreateId;
    this.now = options.now ?? (() => new Date());
    this.records = this.journal?.load().map(restoredRecord) ?? [];
  }

  getState(): CommandControllerState {
    return {
      confirmation: this.confirmation,
      records: this.records,
      refreshingRecordIds: [...this.refreshingRecordIds],
    };
  }

  subscribe(listener: CommandControllerListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  stopTracking(): void {
    this.stopped = true;
    this.operationTracker?.stopAll();
    this.listeners.clear();
  }

  async refreshRecord(recordId: string): Promise<void> {
    if (this.stopped || this.refreshingRecordIds.has(recordId)) {
      return;
    }
    const record = this.records.find(
      (candidate) => candidate.id === recordId,
    );
    if (
      record === undefined ||
      record.operationId === null ||
      this.operationTracker === undefined
    ) {
      return;
    }
    this.refreshingRecordIds.add(recordId);
    this.notify();
    try {
      await this.operationTracker.refresh(record, (updatedRecord) => {
        if (this.stopped) {
          return;
        }
        const visibleRecord = this.persistRecord(updatedRecord)
          ? updatedRecord
          : custodyUnavailableRecord(updatedRecord);
        this.records = this.records.map((candidate) =>
          candidate.id === visibleRecord.id ? visibleRecord : candidate,
        );
        this.notify();
      });
    } finally {
      this.refreshingRecordIds.delete(recordId);
      this.notify();
    }
  }

  startTracking(): void {
    if (this.stopped || this.operationTracker === undefined) {
      return;
    }
    for (const record of this.records) {
      if (record.operationId === null) {
        continue;
      }
      void this.operationTracker.track(record, (updatedRecord) => {
        if (this.stopped) {
          return;
        }
        const visibleRecord = this.persistRecord(updatedRecord)
          ? updatedRecord
          : custodyUnavailableRecord(updatedRecord);
        this.records = this.records.map((candidate) =>
          candidate.id === visibleRecord.id ? visibleRecord : candidate,
        );
        this.notify();
      });
    }
  }

  prepare(command: JobSearchCommand): CommandConfirmation {
    if (this.stopped) {
      throw new Error("This command controller is stopped");
    }
    if (!isMutationAvailable(this.projectionStore)) {
      throw new Error("Mutations require a fresh authenticated snapshot");
    }
    const projectionBinding = outreachApprovalBinding(
      command,
      this.projectionStore,
    );
    const metadata = commandFormMetadata(command.commandName);
    const idempotencyKey = this.createId("idempotency");
    const confirmation: CommandConfirmation = {
      id: idempotencyKey,
      command,
      idempotencyKey,
      correlationId: this.createId("correlation"),
      preparedAt: this.now().toISOString(),
      label: metadata.label,
      consequence: metadata.consequence,
      boundFields: commandBoundFields(command, projectionBinding),
      outreachApprovalBinding: projectionBinding,
      bindingError: null,
      stage: "awaiting-confirmation",
    };
    this.confirmation = confirmation;
    this.notify();
    return confirmation;
  }

  async confirm(confirmationId: string): Promise<void> {
    if (this.stopped) {
      return;
    }
    const confirmation = this.confirmation;
    if (
      confirmation === null ||
      confirmation.id !== confirmationId ||
      confirmation.stage !== "awaiting-confirmation"
    ) {
      return;
    }
    if (!isMutationAvailable(this.projectionStore)) {
      this.notify();
      return;
    }
    if (confirmation.command.commandName === "outreach.approve") {
      let currentBinding: OutreachApprovalBinding | null = null;
      try {
        currentBinding = outreachApprovalBinding(
          confirmation.command,
          this.projectionStore,
        );
      } catch {
        // The actionable guidance below intentionally excludes projection data.
      }
      if (
        !sameOutreachApprovalBinding(
          confirmation.outreachApprovalBinding,
          currentBinding,
        )
      ) {
        this.confirmation = {
          ...confirmation,
          bindingError:
            "The verified outreach binding changed. Refresh projections and start a fresh approval review.",
        };
        this.notify();
        return;
      }
    }
    if (confirmation.command.commandName === "outreach.send") {
      this.confirmation = {
        ...confirmation,
        stage: "awaiting-second-confirmation",
      };
      this.notify();
      return;
    }
    await this.submitConfirmation(confirmation);
  }

  async confirmOutreachSend(
    confirmationId: string,
    approvalContractId: string,
  ): Promise<void> {
    if (this.stopped) {
      return;
    }
    const confirmation = this.confirmation;
    if (
      confirmation === null ||
      confirmation.id !== confirmationId ||
      confirmation.stage !== "awaiting-second-confirmation" ||
      confirmation.command.commandName !== "outreach.send" ||
      confirmation.command.parameters.approvalContractId !==
        approvalContractId
    ) {
      return;
    }
    if (!isMutationAvailable(this.projectionStore)) {
      this.notify();
      return;
    }
    await this.submitConfirmation(confirmation);
  }

  private async submitConfirmation(
    confirmation: CommandConfirmation,
  ): Promise<void> {
    const attemptedAt = this.now().toISOString();
    const approvalContractId =
      confirmation.command.commandName === "outreach.send"
        ? confirmation.command.parameters.approvalContractId
        : null;
    const custodyRecorded = this.writeJournal((journal) => {
      journal.upsert({
        commandName: confirmation.command.commandName,
        idempotencyKey: confirmation.idempotencyKey,
        correlationId: confirmation.correlationId,
        submittedAt: attemptedAt,
        contractId: null,
        operationId: null,
        approvalContractId,
        state: "submitting",
      });
    });
    if (!custodyRecorded) {
      const record: GovernedMutationRecord = {
        id: confirmation.id,
        commandName: confirmation.command.commandName,
        consequence: confirmation.consequence,
        submittedAt: attemptedAt,
        idempotencyKey: confirmation.idempotencyKey,
        correlationId: confirmation.correlationId,
        contractId: null,
        operationId: null,
        state: "failed",
        evidenceStatus: "complete",
        serverReasonCode: null,
        serverReason: null,
        localReason:
          "Command was not sent because local command custody was unavailable. Start a fresh form after checking local storage.",
        completionUnknown: false,
        resubmissionBlocked: true,
        events: [],
        approvalContractId,
        approval: null,
        receipt: null,
        localSignatureVerification: "unavailable",
      };
      this.confirmation = null;
      this.records = [record, ...this.records];
      this.notify();
      return;
    }
    this.confirmation = {
      ...confirmation,
      stage: "submitting",
    };
    this.notify();
    let handle: ContractHandle;
    try {
      const client =
        typeof this.clientProvider === "function"
          ? this.clientProvider()
          : this.clientProvider;
      handle = await submitCommand(client, confirmation.command, {
          idempotencyKey: confirmation.idempotencyKey,
          correlationId: confirmation.correlationId,
        });
    } catch (error) {
      if (
        error instanceof UltradexTimeoutError &&
        error.requestMayHaveCompleted
      ) {
        const record: GovernedMutationRecord = {
          id: confirmation.id,
          commandName: confirmation.command.commandName,
          consequence: confirmation.consequence,
          submittedAt: attemptedAt,
          idempotencyKey: confirmation.idempotencyKey,
          correlationId: confirmation.correlationId,
          contractId: null,
          operationId: null,
          state: "unverifiable",
          evidenceStatus: "unverifiable",
          serverReasonCode: null,
          serverReason: null,
          localReason:
            "Completion unknown. The request may have completed, so this attempt cannot be resubmitted.",
          completionUnknown: true,
          resubmissionBlocked: true,
          events: [],
          approvalContractId: null,
          approval: null,
          receipt: null,
          localSignatureVerification: "unavailable",
        };
        const visibleRecord = this.persistRecord(record)
          ? record
          : custodyUnavailableRecord(record);
        if (this.stopped) {
          return;
        }
        this.confirmation = null;
        this.records = [visibleRecord, ...this.records];
        this.notify();
        return;
      }
      const custodyCleared = this.writeJournal((journal) => {
        journal.remove(confirmation.idempotencyKey);
      });
      const record: GovernedMutationRecord = {
        id: confirmation.id,
        commandName: confirmation.command.commandName,
        consequence: confirmation.consequence,
        submittedAt: attemptedAt,
        idempotencyKey: confirmation.idempotencyKey,
        correlationId: confirmation.correlationId,
        contractId: null,
        operationId: null,
        state: custodyCleared ? "failed" : "unverifiable",
        evidenceStatus: custodyCleared
          ? "complete"
          : "unverifiable",
        serverReasonCode: null,
        serverReason: null,
        localReason: custodyCleared
          ? "Ultradex did not accept this command attempt. Start a fresh form after checking connection and authentication state."
          : "Completion unknown because local command custody could not be cleared. This submitted attempt cannot be resubmitted.",
        completionUnknown: !custodyCleared,
        resubmissionBlocked: true,
        events: [],
        approvalContractId,
        approval: null,
        receipt: null,
        localSignatureVerification: "unavailable",
      };
      if (this.stopped) {
        return;
      }
      this.confirmation = null;
      this.records = [record, ...this.records];
      this.notify();
      return;
    }
    this.confirmation = null;
    const record: GovernedMutationRecord = {
      id: confirmation.id,
      commandName: confirmation.command.commandName,
      consequence: confirmation.consequence,
      submittedAt: handle.submittedAt,
      idempotencyKey: confirmation.idempotencyKey,
      correlationId: confirmation.correlationId,
      contractId: handle.contractId,
      operationId: handle.operationId,
      state: handleState(handle),
      evidenceStatus:
        handle.status === "unverifiable"
          ? "unverifiable"
          : "pending",
      serverReasonCode:
        handle.status === "refused" ? handle.refusalCode : null,
      serverReason:
        handle.status === "refused" ? handle.refusalReason : null,
      localReason: null,
      completionUnknown: false,
      resubmissionBlocked: true,
      events: [],
      approvalContractId,
      approval: null,
      receipt: null,
      localSignatureVerification: "unavailable",
    };
    const visibleRecord = this.persistRecord(record)
      ? record
      : custodyUnavailableRecord(record);
    if (this.stopped) {
      return;
    }
    this.records = [visibleRecord, ...this.records];
    this.notify();
    if (
      visibleRecord.operationId !== null &&
      this.operationTracker !== undefined
    ) {
      await this.operationTracker.track(visibleRecord, (updatedRecord) => {
        if (this.stopped) {
          return;
        }
        const visibleUpdate = this.persistRecord(updatedRecord)
          ? updatedRecord
          : custodyUnavailableRecord(updatedRecord);
        this.records = this.records.map((candidate) =>
          candidate.id === visibleUpdate.id ? visibleUpdate : candidate,
        );
        this.notify();
      });
    }
  }

  private persistRecord(record: GovernedMutationRecord): boolean {
    return this.writeJournal((journal) => {
      journal.upsert({
        commandName: record.commandName,
        idempotencyKey: record.idempotencyKey,
        correlationId: record.correlationId,
        submittedAt: record.submittedAt,
        contractId: record.contractId,
        operationId: record.operationId,
        approvalContractId: record.approvalContractId,
        state: record.state,
      });
    });
  }

  private writeJournal(
    write: (journal: CommandCustodyJournal) => void,
  ): boolean {
    if (this.journal === undefined) {
      return true;
    }
    try {
      write(this.journal);
      return true;
    } catch {
      return false;
    }
  }

  private notify(): void {
    if (this.stopped) {
      return;
    }
    const state = this.getState();
    for (const listener of this.listeners) {
      try {
        listener(state);
      } catch {
        // A host rendering failure must not change command custody.
      }
    }
  }
}
