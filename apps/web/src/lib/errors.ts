import {
  UltradexAuthError,
  UltradexError,
  UltradexGraphQLError,
  UltradexHttpError,
  UltradexSchemaError,
  UltradexTimeoutError,
  UltradexTransportError,
} from "@ultradex/sdk";

/**
 * FR-GW-6 — the glass previously did
 * `error = cause instanceof Error ? cause.message : "Refresh failed"`, which
 * for an UltradexGraphQLError always renders the SDK's hardcoded constant
 * ("Ultradex GraphQL response contained errors", see transport.ts) and
 * throws away the real `errors[]` payload. This module normalizes any
 * thrown value into a short headline plus a full, structured detail list so
 * nothing is ever discarded to a single `.message` string.
 */

export type NormalizedErrorKind =
  | "network"
  | "timeout"
  | "http"
  | "auth-unauthenticated"
  | "auth-missing-scope"
  | "auth-delegation-denied"
  | "auth-unrecognized"
  | "graphql"
  | "schema-invalid-json"
  | "schema-mismatch"
  | "unknown";

export interface NormalizedErrorDetail {
  readonly label: string;
  readonly value: string;
}

export interface NormalizedError {
  /** Short, human-readable summary — safe to render plainly, unquoted. */
  readonly headline: string;
  /** Machine-readable classification for callers that need to branch. */
  readonly kind: NormalizedErrorKind;
  /** Every structured field the SDK gave us, in disclosure order. */
  readonly details: readonly NormalizedErrorDetail[];
}

/**
 * Serialize any value into readable text. Never returns "[object Object]" —
 * objects and arrays are JSON-stringified with indentation; primitives are
 * stringified directly; undefined/null get explicit labels.
 */
function describeValue(value: unknown): string {
  if (value === undefined) {
    return "(none)";
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value instanceof Error) {
    return value.stack ?? value.message;
  }
  try {
    const serialized = JSON.stringify(value, null, 2);
    return serialized ?? String(value);
  } catch {
    return String(value);
  }
}

function describePath(path: readonly (string | number)[] | undefined): string {
  if (path === undefined || path.length === 0) {
    return "(root)";
  }
  return path.join(".");
}

/** FR-GW-4 shape guard: delegation denial is `{code: string, message: string}`. */
function isDelegationDenial(
  value: unknown,
): value is { readonly code: string; readonly message: string } {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  return typeof record.code === "string" && typeof record.message === "string";
}

function normalizeGraphQLError(cause: UltradexGraphQLError): NormalizedError {
  const first = cause.errors[0];
  const headline =
    first !== undefined && first.message.trim().length > 0
      ? first.message
      : "Ultradex GraphQL request failed with no error message.";

  const details: NormalizedErrorDetail[] = [];
  cause.errors.forEach((entry, index) => {
    const suffix = cause.errors.length > 1 ? ` ${index + 1}` : "";
    details.push({ label: `Error${suffix} message`, value: entry.message });
    if (entry.path !== undefined) {
      details.push({ label: `Error${suffix} path`, value: describePath(entry.path) });
    }
    if (entry.extensions !== undefined) {
      details.push({
        label: `Error${suffix} extensions`,
        value: describeValue(entry.extensions),
      });
    }
  });

  return { headline, kind: "graphql", details };
}

function normalizeHttpError(cause: UltradexHttpError): NormalizedError {
  return {
    headline: `Ultradex request failed with HTTP ${cause.status}.`,
    kind: "http",
    details: [
      { label: "Status", value: String(cause.status) },
      { label: "Details", value: describeValue(cause.details) },
    ],
  };
}

function normalizeAuthError(cause: UltradexAuthError): NormalizedError {
  if (cause.status === 401) {
    return {
      headline: "Ultradex rejected the operator token (not authenticated).",
      kind: "auth-unauthenticated",
      details: [
        { label: "Status", value: "401" },
        { label: "Details", value: describeValue(cause.details) },
      ],
    };
  }

  // status === 403: FR-GW-4 requires distinguishing a bare-string detail
  // (missing scope) from a structured {code, message} object (delegation
  // denial) — these are genuinely different failures and must not render
  // identically.
  const { details } = cause;
  if (typeof details === "string") {
    return {
      headline: `Missing required scope: ${details}`,
      kind: "auth-missing-scope",
      details: [
        { label: "Status", value: "403" },
        { label: "Missing scope", value: details },
      ],
    };
  }
  if (isDelegationDenial(details)) {
    return {
      headline: `Delegation denied: ${details.message}`,
      kind: "auth-delegation-denied",
      details: [
        { label: "Status", value: "403" },
        { label: "Denial code", value: details.code },
        { label: "Denial message", value: details.message },
      ],
    };
  }
  return {
    headline: "Ultradex refused the request with HTTP 403.",
    kind: "auth-unrecognized",
    details: [
      { label: "Status", value: "403" },
      { label: "Details", value: describeValue(details) },
    ],
  };
}

function normalizeSchemaError(cause: UltradexSchemaError): NormalizedError {
  const headline =
    cause.reason === "invalid_json"
      ? "Ultradex response was not valid JSON."
      : "Ultradex response did not match its expected contract.";

  const details: NormalizedErrorDetail[] = [{ label: "Reason", value: cause.reason }];
  cause.issues.forEach((issue, index) => {
    details.push({
      label: `Issue ${index + 1}`,
      value: `[${issue.code}] ${describePath(issue.path)}: ${issue.message}`,
    });
  });

  return {
    headline,
    kind: cause.reason === "invalid_json" ? "schema-invalid-json" : "schema-mismatch",
    details,
  };
}

function normalizeTimeoutError(cause: UltradexTimeoutError): NormalizedError {
  return {
    headline: `Ultradex request timed out after ${cause.timeoutMs}ms.`,
    kind: "timeout",
    details: [
      { label: "Timeout (ms)", value: String(cause.timeoutMs) },
      {
        label: "Request may have completed",
        value: String(cause.requestMayHaveCompleted),
      },
    ],
  };
}

function normalizeTransportError(cause: UltradexTransportError): NormalizedError {
  const details: NormalizedErrorDetail[] = [];
  if (cause.cause !== undefined) {
    details.push({ label: "Cause", value: describeValue(cause.cause) });
  }
  return {
    headline: cause.message || "Ultradex transport request failed.",
    kind: "network",
    details,
  };
}

/** Fallback for any UltradexError subclass added later without a specific branch. */
function normalizeUnhandledUltradexError(cause: UltradexError): NormalizedError {
  return {
    headline: cause.message || "Ultradex request failed.",
    kind: "unknown",
    details: [
      { label: "Error type", value: cause.name },
      { label: "Code", value: cause.code },
    ],
  };
}

function normalizePlainError(cause: Error): NormalizedError {
  // A plain `Error` (not thrown by the SDK) carries no structured detail
  // beyond its message, which is already the headline. Attaching a
  // "(unknown)" disclosure that repeats only the class name is not "actual
  // structured detail" — it is noise around a client-side condition (e.g. a
  // missing-token precondition). Leave `details` empty so ErrorBanner
  // renders no disclosure at all for this case.
  return {
    headline: cause.message || "An unexpected error occurred.",
    kind: "unknown",
    details: [],
  };
}

function normalizeUnknownThrow(cause: unknown): NormalizedError {
  return {
    headline: "An unexpected value was thrown.",
    kind: "unknown",
    details: [{ label: "Thrown value", value: describeValue(cause) }],
  };
}

/**
 * Normalize any thrown value from the Ultradex SDK (or elsewhere) into a
 * headline + machine-readable kind + full structured detail list. Every
 * caller in the glass should route caught errors through this function
 * before rendering, per FR-GW-6.
 */
export function normalizeError(cause: unknown): NormalizedError {
  if (cause instanceof UltradexGraphQLError) {
    return normalizeGraphQLError(cause);
  }
  if (cause instanceof UltradexAuthError) {
    return normalizeAuthError(cause);
  }
  if (cause instanceof UltradexHttpError) {
    return normalizeHttpError(cause);
  }
  if (cause instanceof UltradexSchemaError) {
    return normalizeSchemaError(cause);
  }
  if (cause instanceof UltradexTimeoutError) {
    return normalizeTimeoutError(cause);
  }
  if (cause instanceof UltradexTransportError) {
    return normalizeTransportError(cause);
  }
  if (cause instanceof UltradexError) {
    return normalizeUnhandledUltradexError(cause);
  }
  if (cause instanceof Error) {
    return normalizePlainError(cause);
  }
  return normalizeUnknownThrow(cause);
}
