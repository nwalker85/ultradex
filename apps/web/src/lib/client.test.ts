import { describe, expect, it } from "vitest";

import { isCrossOriginApi, operatorAuthMissing } from "./client.js";

describe("operatorAuthMissing", () => {
  it("treats an empty token on the glass origin as deployed proxy auth", () => {
    expect(
      operatorAuthMissing(
        { baseUrl: "http://10.10.20.101:30808", token: "" },
        "http://10.10.20.101:30808",
      ),
    ).toBe(false);
  });

  it("requires a pasted token only when the API origin is somewhere else", () => {
    expect(
      operatorAuthMissing(
        { baseUrl: "http://127.0.0.1:8000", token: "" },
        "http://10.10.20.101:30808",
      ),
    ).toBe(true);
  });

  it("never blocks when a token is already set", () => {
    expect(
      operatorAuthMissing(
        { baseUrl: "http://127.0.0.1:8000", token: "operator-token" },
        "http://10.10.20.101:30808",
      ),
    ).toBe(false);
  });
});

describe("isCrossOriginApi", () => {
  it("is false when origin is unknown (prerender)", () => {
    expect(isCrossOriginApi("http://example.test/api")).toBe(false);
  });
});
