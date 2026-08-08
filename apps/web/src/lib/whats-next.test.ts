import { describe, expect, it } from "vitest";

import { pickWhatsNext } from "./whats-next.js";

describe("pickWhatsNext", () => {
  it("prefers qualified opportunities", () => {
    const next = pickWhatsNext(
      [
        {
          opportunityId: "opportunity-1",
          employer: "Watch Co",
          title: "Role A",
          location: null,
          roleFamily: null,
          status: "watching",
          fitScore: null,
          fitExplanation: null,
          riskFlags: [],
          evidenceRefs: [],
          freshness: {
            sourceEventId: "e",
            sourceEventPosition: "p",
            projectedAt: "2026-08-05T00:00:00Z",
            lagMs: 0,
            status: "fresh",
          },
          createdAt: "2026-08-05T00:00:00Z",
          updatedAt: "2026-08-05T00:00:00Z",
        },
        {
          opportunityId: "opportunity-2",
          employer: "Amelia",
          title: "Leadership",
          location: null,
          roleFamily: null,
          status: "qualified",
          fitScore: null,
          fitExplanation: null,
          riskFlags: [],
          evidenceRefs: [],
          freshness: {
            sourceEventId: "e",
            sourceEventPosition: "p",
            projectedAt: "2026-08-05T00:00:00Z",
            lagMs: 0,
            status: "fresh",
          },
          createdAt: "2026-08-05T00:00:00Z",
          updatedAt: "2026-08-05T00:00:00Z",
        },
      ],
      [],
    );
    expect(next.id).toBe("opportunity-2");
    expect(next.kind).toBe("opportunity");
  });
});
