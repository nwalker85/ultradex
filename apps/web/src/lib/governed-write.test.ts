import { describe, expect, it } from "vitest";
import {
  UltradexAuthError,
  UltradexHttpError,
  UltradexTimeoutError,
  UltradexTransportError,
  type ContractHandle,
} from "@ultradex/sdk";

import {
  cannedReasonCopy,
  classifySubmitError,
  classifySubmittedHandle,
  contractStatusTone,
  isTerminalContractStatus,
  isTerminalOperationStatus,
  newIdempotencyKey,
  nextPollDelayMs,
  operationTone,
  POLL_BASE_MS,
  POLL_MAX_MS,
  submitGoverned,
  tier1OutcomeCopy,
  tier1OutcomeTone,
  toBannerTone,
} from "./governed-write.js";

function handle(overrides: Partial<ContractHandle> & { status: ContractHandle["status"] }): ContractHandle {
  return {
    contractId: "contract-1",
    operationId: "operation-1",
    submittedAt: "2026-08-08T00:00:00Z",
    correlationId: "correlation-1",
    ...overrides,
  } as ContractHandle;
}

describe("newIdempotencyKey", () => {
  it("FR-GW-1: mints a fresh key every call, never reusing one", () => {
    const keys = new Set(Array.from({ length: 20 }, () => newIdempotencyKey()));
    expect(keys.size).toBe(20);
  });
});

describe("isTerminalContractStatus / contractStatusTone", () => {
  it("treats accepted, pending, running, partial, compensating as non-terminal", () => {
    for (const status of ["accepted", "pending", "running", "partial", "compensating"] as const) {
      expect(isTerminalContractStatus(status)).toBe(false);
    }
  });

  it("FR-GW-2: treats a 503-shaped failed handle as terminal with danger tone", () => {
    expect(isTerminalContractStatus("failed")).toBe(true);
    expect(contractStatusTone("failed")).toBe("danger");
  });

  it("FR-OPS-3: refused is warning-toned, never danger", () => {
    expect(contractStatusTone("refused")).toBe("warning");
  });

  it("succeeded is success-toned", () => {
    expect(contractStatusTone("succeeded")).toBe("success");
  });

  it("NFR-6: an unmapped terminal status falls back to a labeled neutral tone, never throws", () => {
    expect(() => contractStatusTone("unverifiable")).not.toThrow();
    expect(contractStatusTone("unverifiable")).toBe("neutral");
  });
});

describe("classifySubmittedHandle", () => {
  it("classifies an accepted 202 handle as accepted (proceeds to Tier 2 polling)", () => {
    const outcome = classifySubmittedHandle(handle({ status: "accepted" }));
    expect(outcome.kind).toBe("accepted");
  });

  it("FR-GW-2: classifies a 503-shaped failed handle as already-terminal, danger tone, no polling implied", () => {
    const outcome = classifySubmittedHandle(handle({ status: "failed" }));
    expect(outcome.kind).toBe("already-terminal");
    expect(outcome).toMatchObject({ tone: "danger" });
  });
});

describe("classifySubmitError", () => {
  it("FR-GW-3: 409 classifies as conflict, keeping the composer implicitly open (no form reset implied)", () => {
    const outcome = classifySubmitError(
      new UltradexHttpError(409, { code: "idempotency_conflict", message: "reused key" }),
    );
    expect(outcome.kind).toBe("conflict");
  });

  it("FR-GW-4: bare-string 403 detail classifies as missing scope", () => {
    const outcome = classifySubmitError(
      new UltradexAuthError(403, "Credential lacks required scope: command:opportunities.create"),
    );
    expect(outcome.kind).toBe("auth-missing-scope");
  });

  it("FR-GW-4: structured {code, message} 403 detail classifies as delegation denial", () => {
    const outcome = classifySubmitError(
      new UltradexAuthError(403, {
        code: "command_authority_refused",
        message: "Command authority refused",
      }),
    );
    expect(outcome.kind).toBe("auth-delegation-denied");
  });

  it("FR-GW-4: the two 403 shapes never classify the same way", () => {
    const missingScope = classifySubmitError(new UltradexAuthError(403, "some scope"));
    const delegationDenied = classifySubmitError(
      new UltradexAuthError(403, { code: "x", message: "y" }),
    );
    expect(missingScope.kind).not.toBe(delegationDenied.kind);
  });

  it("FR-GW-5: timeout classifies as network-unclear", () => {
    const outcome = classifySubmitError(new UltradexTimeoutError(10_000, true));
    expect(outcome.kind).toBe("network-unclear");
  });

  it("FR-GW-5: transport failure classifies as network-unclear", () => {
    const outcome = classifySubmitError(new UltradexTransportError());
    expect(outcome.kind).toBe("network-unclear");
  });

  it("falls back to a generic error classification for anything else", () => {
    const outcome = classifySubmitError(new UltradexHttpError(422, "bad parameters"));
    expect(outcome.kind).toBe("error");
  });
});

describe("tier1OutcomeCopy / tier1OutcomeTone", () => {
  it("FR-GW-5: network-unclear copy states plainly it is unclear whether the request was received, and never suggests retrying automatically", () => {
    const outcome = classifySubmitError(new UltradexTransportError());
    const copy = tier1OutcomeCopy(outcome);
    expect(copy).toContain("Unclear whether this was received");
    expect(copy?.toLowerCase()).not.toContain("retrying now");
  });

  it("FR-GW-3: conflict copy says already submitted and is warning-toned, not danger", () => {
    const outcome = classifySubmitError(new UltradexHttpError(409, "reused"));
    expect(tier1OutcomeCopy(outcome)).toContain("Already submitted");
    expect(tier1OutcomeTone(outcome)).toBe("warning");
  });

  it("FR-GW-4: missing-scope and delegation-denial copy read differently", () => {
    const missingScope = classifySubmitError(new UltradexAuthError(403, "scope"));
    const delegationDenied = classifySubmitError(
      new UltradexAuthError(403, { code: "x", message: "y" }),
    );
    expect(tier1OutcomeCopy(missingScope)).not.toBe(tier1OutcomeCopy(delegationDenied));
  });

  it("returns null for an accepted/already-terminal outcome (no Tier 1 banner needed)", () => {
    expect(tier1OutcomeCopy(classifySubmittedHandle(handle({ status: "accepted" })))).toBeNull();
  });
});

describe("isTerminalOperationStatus / operationTone", () => {
  it("completed, failed, refused are terminal; pending, running are not", () => {
    expect(isTerminalOperationStatus("completed")).toBe(true);
    expect(isTerminalOperationStatus("failed")).toBe(true);
    expect(isTerminalOperationStatus("refused")).toBe(true);
    expect(isTerminalOperationStatus("pending")).toBe(false);
    expect(isTerminalOperationStatus("running")).toBe(false);
  });

  it("FR-OPS-3: refused is warning-toned, danger is reserved for failed", () => {
    expect(operationTone("refused")).toBe("warning");
    expect(operationTone("failed")).toBe("danger");
    expect(operationTone("refused")).not.toBe("danger");
  });

  it("completed is success-toned", () => {
    expect(operationTone("completed")).toBe("success");
  });
});

describe("nextPollDelayMs", () => {
  it("FR-GW-7: starts at the 1.5s base", () => {
    expect(nextPollDelayMs(0)).toBe(POLL_BASE_MS);
  });

  it("increases with each attempt", () => {
    expect(nextPollDelayMs(1)).toBeGreaterThan(nextPollDelayMs(0));
    expect(nextPollDelayMs(2)).toBeGreaterThan(nextPollDelayMs(1));
  });

  it("is capped and never exceeds the cap however high the attempt count", () => {
    expect(nextPollDelayMs(50)).toBe(POLL_MAX_MS);
    expect(nextPollDelayMs(1000)).toBeLessThanOrEqual(POLL_MAX_MS);
  });

  it("never returns a delay below the base for any non-negative attempt", () => {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      expect(nextPollDelayMs(attempt)).toBeGreaterThanOrEqual(POLL_BASE_MS);
    }
  });
});

describe("cannedReasonCopy (FR-OPS-5)", () => {
  it("provides plain-language copy for each of the four *_unbound codes", () => {
    for (const code of [
      "scorer_unbound",
      "relationship_resolver_unbound",
      "source_adapter_unbound",
      "delivery_transport_unbound",
    ]) {
      const copy = cannedReasonCopy(code);
      expect(copy).not.toBeNull();
      expect(copy?.toLowerCase()).not.toBe(code);
    }
  });

  it("returns null for a code with no canned copy, rather than a fake explanation", () => {
    expect(cannedReasonCopy("opportunity_not_found")).toBeNull();
  });

  it("returns null for a null reason code", () => {
    expect(cannedReasonCopy(null)).toBeNull();
  });
});

describe("submitGoverned", () => {
  it("FR-GW-1: passes a fresh idempotency key to the submit function", async () => {
    let seenKey = "";
    await submitGoverned(async (idempotencyKey) => {
      seenKey = idempotencyKey;
      return handle({ status: "accepted" });
    });
    expect(seenKey.length).toBeGreaterThan(0);
  });

  it("classifies a returned accepted handle as the accepted outcome with a null error", async () => {
    const result = await submitGoverned(async () => handle({ status: "accepted" }));
    expect(result.outcome.kind).toBe("accepted");
    expect(result.error).toBeNull();
  });

  it("classifies a thrown error via classifySubmitError and preserves the raw cause for ErrorBanner", async () => {
    const cause = new UltradexHttpError(409, "reused");
    const result = await submitGoverned(async () => {
      throw cause;
    });
    expect(result.outcome.kind).toBe("conflict");
    expect(result.error).toBe(cause);
  });

  it("never reuses an idempotency key across two calls", async () => {
    const keys: string[] = [];
    const capture = async (key: string): Promise<ContractHandle> => {
      keys.push(key);
      return handle({ status: "accepted" });
    };
    await submitGoverned(capture);
    await submitGoverned(capture);
    expect(keys[0]).not.toBe(keys[1]);
  });
});

describe("toBannerTone", () => {
  it("maps neutral to info (Banner has no neutral tone) and passes the rest through unchanged", () => {
    expect(toBannerTone("neutral")).toBe("info");
    expect(toBannerTone("success")).toBe("success");
    expect(toBannerTone("warning")).toBe("warning");
    expect(toBannerTone("danger")).toBe("danger");
  });
});
