import {
  UltradexAuthError,
  UltradexHttpError,
  UltradexTimeoutError,
  UltradexTransportError,
  type ContractHandle,
  type ContractStatus,
  type OperationStatus,
} from "@ultradex/sdk";

import { normalizeError, type NormalizedError } from "./errors.js";

/**
 * The governed-write pattern (PRD section 8). Every write screen submits
 * through Tier 1 (`classifySubmittedHandle` / `classifySubmitError`) and
 * resolves through Tier 2 (`OperationTrackerState`, in
 * `operation-tracker.svelte.ts`). This module holds the framework-agnostic
 * classification and timing logic so it is unit-testable without a DOM.
 */

export type Tone = "success" | "danger" | "warning" | "neutral";

// ---------------------------------------------------------------------------
// FR-GW-1 — fresh idempotency key per attempt, never reused on retry.
// ---------------------------------------------------------------------------

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

// ---------------------------------------------------------------------------
// Tier 1: submission acknowledgment (section 8.1)
// ---------------------------------------------------------------------------

/**
 * `submit()` on the SDK's command executor only *returns* a ContractHandle
 * for HTTP 202 (accepted) and 503 (dispatch failure — already terminal, see
 * `_record_dispatch_failure`); every other non-2xx status is a thrown
 * `UltradexHttpError`/`UltradexAuthError`. A handle with `status !==
 * "accepted"` is therefore already resolved — FR-GW-2 requires rendering it
 * immediately with no polling loop.
 */
const NON_TERMINAL_CONTRACT_STATUSES: ReadonlySet<ContractStatus> = new Set([
  "accepted",
  "pending",
  "running",
  "partial",
  "compensating",
]);

export function isTerminalContractStatus(status: ContractStatus): boolean {
  return !NON_TERMINAL_CONTRACT_STATUSES.has(status);
}

const CONTRACT_STATUS_TONE: Readonly<Partial<Record<ContractStatus, Tone>>> = {
  succeeded: "success",
  failed: "danger",
  refused: "warning",
  cancelled: "danger",
  expired: "neutral",
  revoked: "neutral",
  unverifiable: "neutral",
};

/** NFR-6 — an unrecognized terminal contract status renders a labeled fallback, never blank or thrown. */
export function contractStatusTone(status: ContractStatus): Tone {
  return CONTRACT_STATUS_TONE[status] ?? "neutral";
}

export type Tier1Outcome =
  | { readonly kind: "accepted"; readonly handle: ContractHandle }
  | { readonly kind: "already-terminal"; readonly handle: ContractHandle; readonly tone: Tone }
  | { readonly kind: "conflict"; readonly normalized: NormalizedError }
  | { readonly kind: "auth-missing-scope"; readonly normalized: NormalizedError }
  | { readonly kind: "auth-delegation-denied"; readonly normalized: NormalizedError }
  | { readonly kind: "network-unclear"; readonly normalized: NormalizedError }
  | { readonly kind: "error"; readonly normalized: NormalizedError };

/** Classifies a handle `submit()` *returned* (202 or 503 — never throws for either). */
export function classifySubmittedHandle(handle: ContractHandle): Tier1Outcome {
  if (handle.status === "accepted") {
    return { kind: "accepted", handle };
  }
  // FR-GW-2: e.g. the 503 dispatch-failure path — already a terminal
  // "failed" contract. Do not start a Tier 2 polling loop for this.
  return {
    kind: "already-terminal",
    handle,
    tone: contractStatusTone(handle.status),
  };
}

/** Classifies whatever `submit()` *threw* (409 / 403 / 422 / network / timeout / schema). */
export function classifySubmitError(error: unknown): Tier1Outcome {
  const normalized = normalizeError(error);

  // FR-GW-3: idempotency-key reuse. No new operation was created.
  if (error instanceof UltradexHttpError && error.status === 409) {
    return { kind: "conflict", normalized };
  }

  // FR-GW-4: 403 shape distinguishes missing scope (bare string) from a
  // delegation denial (structured {code, message}) — normalizeError already
  // performs this shape check; branch on its result.
  if (error instanceof UltradexAuthError && error.status === 403) {
    return normalized.kind === "auth-delegation-denied"
      ? { kind: "auth-delegation-denied", normalized }
      : { kind: "auth-missing-scope", normalized };
  }

  // FR-GW-5: transport failure or timeout — whether the write was received
  // is genuinely unknown. Never auto-retry.
  if (error instanceof UltradexTimeoutError || error instanceof UltradexTransportError) {
    return { kind: "network-unclear", normalized };
  }

  return { kind: "error", normalized };
}

/** Plain-language line shown above the full ErrorBanner disclosure for each Tier 1 outcome. */
export function tier1OutcomeCopy(outcome: Tier1Outcome): string | null {
  switch (outcome.kind) {
    case "conflict":
      return "Already submitted. This idempotency key was already used and no new operation was created — check Operations for the original attempt.";
    case "auth-missing-scope":
      return "This operator token is missing the scope this command requires.";
    case "auth-delegation-denied":
      return "The delegation behind this token does not permit this command.";
    case "network-unclear":
      return "Unclear whether this was received. Check Operations before resubmitting — this will not retry automatically.";
    default:
      return null;
  }
}

/** Banner tone for the plain-language Tier 1 line. Never the danger tone for a conflict (it is not a failure). */
export function tier1OutcomeTone(outcome: Tier1Outcome): Tone {
  switch (outcome.kind) {
    case "conflict":
      return "warning";
    case "network-unclear":
      return "warning";
    case "auth-missing-scope":
    case "auth-delegation-denied":
      return "danger";
    default:
      return "neutral";
  }
}

// ---------------------------------------------------------------------------
// Tier 2: domain outcome (section 8.2)
// ---------------------------------------------------------------------------

const OPERATION_TERMINAL_STATUSES: ReadonlySet<OperationStatus> = new Set([
  "completed",
  "failed",
  "refused",
]);

export function isTerminalOperationStatus(status: OperationStatus): boolean {
  return OPERATION_TERMINAL_STATUSES.has(status);
}

const OPERATION_TONE: Readonly<Record<OperationStatus, Tone>> = {
  pending: "neutral",
  running: "neutral",
  completed: "success",
  // FR-OPS-3: `refused` is a governance decision working correctly — warning,
  // never danger. Danger is reserved for `failed`.
  refused: "warning",
  failed: "danger",
};

export function operationTone(status: OperationStatus): Tone {
  return OPERATION_TONE[status] ?? "neutral";
}

/** 1.5s base with capped exponential backoff (FR-GW-7). `attempt` is 0-indexed. */
export const POLL_BASE_MS = 1500;
export const POLL_MAX_MS = 8000;
const POLL_BACKOFF_FACTOR = 1.5;

export function nextPollDelayMs(attempt: number): number {
  const safeAttempt = Math.max(0, attempt);
  const raw = POLL_BASE_MS * POLL_BACKOFF_FACTOR ** safeAttempt;
  return Math.min(Math.round(raw), POLL_MAX_MS);
}

// ---------------------------------------------------------------------------
// FR-OPS-5 — canned, plain-language copy for the four *_unbound refusal
// codes. These land in `Operation.error` (the granular reason code).
// ---------------------------------------------------------------------------

const UNBOUND_REASON_COPY: Readonly<Record<string, string>> = {
  scorer_unbound:
    "No scoring adapter is bound yet. Nothing is bound to execute this action — this refusal is the system working correctly, not a bug.",
  relationship_resolver_unbound:
    "No relationship-resolution adapter is bound yet. Nothing is bound to execute this action — this refusal is the system working correctly, not a bug.",
  source_adapter_unbound:
    "No source-ingestion adapter is bound yet. Nothing is bound to execute this action — this refusal is the system working correctly, not a bug.",
  delivery_transport_unbound:
    "No delivery connector is bound yet. The approval, the commitment, and this refusal are all durably recorded; nothing was sent, and nothing was lost.",
};

export function cannedReasonCopy(reasonCode: string | null): string | null {
  if (reasonCode === null) {
    return null;
  }
  return UNBOUND_REASON_COPY[reasonCode] ?? null;
}

// ---------------------------------------------------------------------------
// Shared submission helper — every composer (create, score, sync, …) drives
// Tier 1 through this one function so the classification logic above is
// exercised identically everywhere, per the brief: reusable components, not
// per-form reimplementation.
// ---------------------------------------------------------------------------

export interface GovernedSubmitResult {
  readonly outcome: Tier1Outcome;
  /** The raw thrown value, if any — pass straight to ErrorBanner (FR-GW-6). Null on success. */
  readonly error: unknown | null;
}

export async function submitGoverned(
  submit: (idempotencyKey: string) => Promise<ContractHandle>,
): Promise<GovernedSubmitResult> {
  const idempotencyKey = newIdempotencyKey();
  try {
    const result = await submit(idempotencyKey);
    return { outcome: classifySubmittedHandle(result), error: null };
  } catch (cause) {
    return { outcome: classifySubmitError(cause), error: cause };
  }
}

/** Banner only accepts info|success|warning|danger — this pattern's neutral tone maps to info. */
export function toBannerTone(tone: Tone): "info" | "success" | "warning" | "danger" {
  return tone === "neutral" ? "info" : tone;
}
