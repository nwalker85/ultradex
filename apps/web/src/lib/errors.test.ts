import { describe, expect, it } from "vitest";
import {
  UltradexAuthError,
  UltradexGraphQLError,
  UltradexHttpError,
  UltradexSchemaError,
  UltradexTimeoutError,
  UltradexTransportError,
} from "@ultradex/sdk";

import { normalizeError } from "./errors.js";

describe("normalizeError", () => {
  it("surfaces the real GraphQL error message as the headline, not the SDK's generic constant", () => {
    const cause = new UltradexGraphQLError([
      {
        message: "connection to server at postgres failed",
        path: ["opportunities", 0, "employer"],
        extensions: { code: "DATABASE_UNAVAILABLE" },
      },
    ]);

    const normalized = normalizeError(cause);

    expect(normalized.headline).toBe("connection to server at postgres failed");
    expect(normalized.headline).not.toBe(cause.message);
    expect(normalized.kind).toBe("graphql");
    expect(normalized.details).toContainEqual({
      label: "Error message",
      value: "connection to server at postgres failed",
    });
    expect(normalized.details).toContainEqual({
      label: "Error path",
      value: "opportunities.0.employer",
    });
    expect(normalized.details.some((d) => d.value.includes("DATABASE_UNAVAILABLE"))).toBe(
      true,
    );
  });

  it("indexes detail labels when multiple GraphQL errors are present", () => {
    const cause = new UltradexGraphQLError([
      { message: "first problem" },
      { message: "second problem" },
    ]);

    const normalized = normalizeError(cause);

    expect(normalized.details).toContainEqual({ label: "Error 1 message", value: "first problem" });
    expect(normalized.details).toContainEqual({ label: "Error 2 message", value: "second problem" });
  });

  it("normalizes UltradexHttpError with status and details, never [object Object]", () => {
    const cause = new UltradexHttpError(503, { reason: "dispatch failure" });

    const normalized = normalizeError(cause);

    expect(normalized.kind).toBe("http");
    expect(normalized.headline).toContain("503");
    const detailValues = normalized.details.map((d) => d.value).join("\n");
    expect(detailValues).not.toContain("[object Object]");
    expect(detailValues).toContain("dispatch failure");
  });

  it("treats a 401 as unauthenticated, distinct from 403 kinds", () => {
    const cause = new UltradexAuthError(401, "no token supplied");

    const normalized = normalizeError(cause);

    expect(normalized.kind).toBe("auth-unauthenticated");
  });

  it("FR-GW-4: distinguishes a bare-string 403 detail (missing scope) from a structured denial", () => {
    const missingScope = normalizeError(
      new UltradexAuthError(403, "command:opportunities.create"),
    );
    const delegationDenial = normalizeError(
      new UltradexAuthError(403, {
        code: "delegation_denied",
        message: "acting principal is not permitted",
      }),
    );

    expect(missingScope.kind).toBe("auth-missing-scope");
    expect(delegationDenial.kind).toBe("auth-delegation-denied");
    expect(missingScope.kind).not.toBe(delegationDenial.kind);
    expect(missingScope.headline).not.toBe(delegationDenial.headline);
    expect(delegationDenial.details).toContainEqual({
      label: "Denial code",
      value: "delegation_denied",
    });
  });

  it("falls back to a labeled-unrecognized kind for an unexpected 403 shape", () => {
    const normalized = normalizeError(new UltradexAuthError(403, 42));

    expect(normalized.kind).toBe("auth-unrecognized");
  });

  it("normalizes UltradexSchemaError issues distinctly by reason", () => {
    const invalidJson = normalizeError(new UltradexSchemaError("invalid_json"));
    expect(invalidJson.kind).toBe("schema-invalid-json");

    const mismatch = normalizeError(
      new UltradexSchemaError("schema_mismatch", [
        { code: "invalid_type", message: "expected string", path: ["data", "id"] },
      ]),
    );
    expect(mismatch.kind).toBe("schema-mismatch");
    expect(mismatch.details.some((d) => d.value.includes("data.id"))).toBe(true);
  });

  it("normalizes timeout errors with the machine-readable completion flag", () => {
    const normalized = normalizeError(new UltradexTimeoutError(10_000, true));

    expect(normalized.kind).toBe("timeout");
    expect(normalized.details).toContainEqual({
      label: "Request may have completed",
      value: "true",
    });
  });

  it("normalizes transport errors as network failures", () => {
    const normalized = normalizeError(new UltradexTransportError());

    expect(normalized.kind).toBe("network");
  });

  it("falls back to the message for a plain Error", () => {
    const normalized = normalizeError(new Error("boom"));

    expect(normalized.kind).toBe("unknown");
    expect(normalized.headline).toBe("boom");
  });

  it("never renders [object Object] for a non-Error thrown value", () => {
    const normalized = normalizeError({ weird: "shape", nested: { n: 1 } });

    expect(normalized.kind).toBe("unknown");
    const rendered = [normalized.headline, ...normalized.details.map((d) => d.value)].join("\n");
    expect(rendered).not.toContain("[object Object]");
    expect(rendered).toContain("weird");
  });
});
