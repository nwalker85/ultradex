import type { JobSearchCommandName } from "@ultradex/sdk";

import type { ObsidianSecretStorage } from "../settings.js";
import type { GovernedOutcomeState } from "./operation-tracker.js";

export const COMMAND_CUSTODY_SECRET_ID =
  "ultradex-command-custody-v1";

const COMMAND_CUSTODY_JOURNAL_VERSION = 1;
const ABSOLUTE_MAX_ENTRIES = 50;
const DEFAULT_MAX_ENTRIES = ABSOLUTE_MAX_ENTRIES;
const MAX_IDENTIFIER_LENGTH = 512;
const ENTRY_KEYS = new Set([
  "commandName",
  "idempotencyKey",
  "correlationId",
  "submittedAt",
  "contractId",
  "operationId",
  "approvalContractId",
  "state",
]);
const COMMAND_NAMES = new Set<JobSearchCommandName>([
  "sources.ingest",
  "opportunities.create",
  "opportunities.score",
  "applications.transition",
  "relationships.sync",
  "outreach.prepare",
  "outreach.approve",
  "outreach.send",
  "evidence.export",
]);
const CUSTODY_STATES = new Set<CommandCustodyJournalState>([
  "submitting",
  "accepted",
  "pending",
  "running",
  "approval-required",
  "refused",
  "failed",
  "succeeded",
  "unverifiable",
]);

export type CommandCustodyJournalState =
  | "submitting"
  | GovernedOutcomeState;

export interface CommandCustodyJournalEntry {
  readonly commandName: JobSearchCommandName;
  readonly idempotencyKey: string;
  readonly correlationId: string;
  readonly submittedAt: string;
  readonly contractId: string | null;
  readonly operationId: string | null;
  readonly approvalContractId: string | null;
  readonly state: CommandCustodyJournalState;
}

export interface CommandCustodyJournalOptions {
  readonly maxEntries?: number;
}

function isObject(
  value: unknown,
): value is Readonly<Record<string, unknown>> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function isBoundedIdentifier(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= MAX_IDENTIFIER_LENGTH
  );
}

function isNullableIdentifier(value: unknown): value is string | null {
  return value === null || isBoundedIdentifier(value);
}

function hasValidStateIdentifiers(
  state: CommandCustodyJournalState,
  contractId: string | null,
  operationId: string | null,
): boolean {
  const hasBothIdentifiers =
    contractId !== null && operationId !== null;
  const hasNeitherIdentifier =
    contractId === null && operationId === null;
  if (state === "submitting") {
    return hasNeitherIdentifier;
  }
  if (state === "unverifiable") {
    return hasBothIdentifiers || hasNeitherIdentifier;
  }
  return hasBothIdentifiers;
}

function parseEntry(value: unknown): CommandCustodyJournalEntry | null {
  if (!isObject(value)) {
    return null;
  }
  const keys = Object.keys(value);
  if (
    keys.length !== ENTRY_KEYS.size ||
    keys.some((key) => !ENTRY_KEYS.has(key))
  ) {
    return null;
  }
  if (
    typeof value.commandName !== "string" ||
    !COMMAND_NAMES.has(value.commandName as JobSearchCommandName) ||
    !isBoundedIdentifier(value.idempotencyKey) ||
    !isBoundedIdentifier(value.correlationId) ||
    typeof value.submittedAt !== "string" ||
    value.submittedAt.length > 64 ||
    Number.isNaN(Date.parse(value.submittedAt)) ||
    !isNullableIdentifier(value.contractId) ||
    !isNullableIdentifier(value.operationId) ||
    !isNullableIdentifier(value.approvalContractId) ||
    typeof value.state !== "string" ||
    !CUSTODY_STATES.has(value.state as CommandCustodyJournalState)
  ) {
    return null;
  }
  if (
    !hasValidStateIdentifiers(
      value.state as CommandCustodyJournalState,
      value.contractId,
      value.operationId,
    )
  ) {
    return null;
  }
  return {
    commandName: value.commandName as JobSearchCommandName,
    idempotencyKey: value.idempotencyKey,
    correlationId: value.correlationId,
    submittedAt: value.submittedAt,
    contractId: value.contractId,
    operationId: value.operationId,
    approvalContractId: value.approvalContractId,
    state: value.state as CommandCustodyJournalState,
  };
}

export class CommandCustodyJournal {
  private readonly maxEntries: number;

  constructor(
    private readonly secretStorage: ObsidianSecretStorage | undefined,
    options: CommandCustodyJournalOptions = {},
  ) {
    const configuredMax = options.maxEntries ?? DEFAULT_MAX_ENTRIES;
    this.maxEntries =
      Number.isInteger(configuredMax) && configuredMax > 0
        ? Math.min(configuredMax, ABSOLUTE_MAX_ENTRIES)
        : DEFAULT_MAX_ENTRIES;
  }

  load(): readonly CommandCustodyJournalEntry[] {
    if (this.secretStorage === undefined) {
      return [];
    }
    const serialized = this.secretStorage.getSecret(
      COMMAND_CUSTODY_SECRET_ID,
    );
    if (serialized === null) {
      return [];
    }
    try {
      const value: unknown = JSON.parse(serialized);
      if (
        !isObject(value) ||
        Object.keys(value).length !== 2 ||
        value.version !== COMMAND_CUSTODY_JOURNAL_VERSION ||
        !Array.isArray(value.entries) ||
        value.entries.length > this.maxEntries
      ) {
        return [];
      }
      const entries = value.entries.map(parseEntry);
      if (entries.some((entry) => entry === null)) {
        return [];
      }
      return entries as readonly CommandCustodyJournalEntry[];
    } catch {
      return [];
    }
  }

  upsert(entry: CommandCustodyJournalEntry): void {
    if (this.secretStorage === undefined) {
      return;
    }
    const safeEntry = parseEntry(entry);
    if (safeEntry === null) {
      throw new Error("Invalid command custody entry");
    }
    const entries = [
      safeEntry,
      ...this.load().filter(
        (candidate) =>
          candidate.idempotencyKey !== safeEntry.idempotencyKey,
      ),
    ].slice(0, this.maxEntries);
    this.secretStorage.setSecret(
      COMMAND_CUSTODY_SECRET_ID,
      JSON.stringify({
        version: COMMAND_CUSTODY_JOURNAL_VERSION,
        entries,
      }),
    );
  }

  remove(idempotencyKey: string): void {
    if (this.secretStorage === undefined) {
      return;
    }
    if (!isBoundedIdentifier(idempotencyKey)) {
      throw new Error("Invalid command custody key");
    }
    const entries = this.load()
      .filter(
        (candidate) =>
          candidate.idempotencyKey !== idempotencyKey,
      )
      .slice(0, this.maxEntries);
    this.secretStorage.setSecret(
      COMMAND_CUSTODY_SECRET_ID,
      JSON.stringify({
        version: COMMAND_CUSTODY_JOURNAL_VERSION,
        entries,
      }),
    );
  }
}
