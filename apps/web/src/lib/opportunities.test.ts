import { describe, expect, it } from "vitest";

import { findOpportunityById, opportunitiesEmptyState, OPPORTUNITY_STATUS_FILTERS } from "./opportunities.js";
import type { Opportunity } from "@ultradex/sdk";

function opportunity(overrides: Partial<Opportunity> & { opportunityId: string }): Opportunity {
  return {
    employer: "Watch Co",
    title: "Role",
    location: null,
    roleFamily: null,
    status: "discovered",
    fitScore: null,
    fitExplanation: null,
    riskFlags: [],
    evidenceRefs: [],
    freshness: {
      sourceEventId: "e",
      sourceEventPosition: "p",
      projectedAt: "2026-08-08T00:00:00Z",
      lagMs: 0,
      status: "fresh",
    },
    createdAt: "2026-08-08T00:00:00Z",
    updatedAt: "2026-08-08T00:00:00Z",
    ...overrides,
  } as Opportunity;
}

describe("OPPORTUNITY_STATUS_FILTERS", () => {
  it("FR-OPP-1: offers exactly discovered, qualified, watching — never archived", () => {
    expect(OPPORTUNITY_STATUS_FILTERS).toEqual(["discovered", "qualified", "watching"]);
    expect(OPPORTUNITY_STATUS_FILTERS).not.toContain("archived");
  });
});

describe("opportunitiesEmptyState (FR-OPP-2)", () => {
  it("true-zero (no filter) and filtered-zero (a status filter) never share copy", () => {
    const trueZero = opportunitiesEmptyState("");
    for (const status of OPPORTUNITY_STATUS_FILTERS) {
      const filteredZero = opportunitiesEmptyState(status);
      expect(filteredZero.title).not.toBe(trueZero.title);
      expect(filteredZero.description).not.toBe(trueZero.description);
    }
  });

  it("true-zero is tagged for a create action, filtered-zero for a clear-filter action", () => {
    expect(opportunitiesEmptyState("").kind).toBe("true-zero");
    expect(opportunitiesEmptyState("discovered").kind).toBe("filtered-zero");
  });

  it("filtered-zero copy names the active filter", () => {
    expect(opportunitiesEmptyState("qualified").title).toContain("qualified");
    expect(opportunitiesEmptyState("watching").title).toContain("watching");
  });

  it("no two distinct filters share identical filtered-zero copy by accident", () => {
    const titles = OPPORTUNITY_STATUS_FILTERS.map((status) => opportunitiesEmptyState(status).title);
    expect(new Set(titles).size).toBe(titles.length);
  });
});

describe("findOpportunityById (FR-OPP-3 fallback)", () => {
  const items = [opportunity({ opportunityId: "a" }), opportunity({ opportunityId: "b" })];

  it("finds a matching opportunity by id", () => {
    expect(findOpportunityById(items, "b")?.opportunityId).toBe("b");
  });

  it("returns null, never throws, on a miss", () => {
    expect(findOpportunityById(items, "missing")).toBeNull();
  });

  it("returns null on an empty list", () => {
    expect(findOpportunityById([], "a")).toBeNull();
  });
});
