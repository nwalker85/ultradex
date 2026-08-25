import { describe, expect, it } from "vitest";
import type { Opportunity } from "@ultradex/sdk";

import {
  compareOpportunitiesByScoreDescNullsLast,
  isExcludedOpportunity,
  partitionOpportunitiesForList,
  rankOpportunitiesByScore,
} from "./opportunity-ranking.js";

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
      projectedAt: "2026-08-16T00:00:00Z",
      lagMs: 0,
      status: "fresh",
    },
    createdAt: "2026-08-16T00:00:00Z",
    updatedAt: "2026-08-16T00:00:00Z",
    ...overrides,
  } as Opportunity;
}

describe("isExcludedOpportunity", () => {
  it("is true when fitExplanation starts with 'excluded'", () => {
    expect(
      isExcludedOpportunity(
        opportunity({
          opportunityId: "a",
          fitScore: 0,
          fitExplanation: "excluded: employer in exclusions (current employer) — 'Acme' matches 'Acme'",
        }),
      ),
    ).toBe(true);
  });

  it("is case-insensitive on the prefix", () => {
    expect(
      isExcludedOpportunity(opportunity({ opportunityId: "a", fitExplanation: "Excluded: reasons" })),
    ).toBe(true);
  });

  it("is false for a genuinely scored explanation, even at score 0", () => {
    expect(
      isExcludedOpportunity(
        opportunity({
          opportunityId: "a",
          fitScore: 0,
          fitExplanation: "role_family no match (weight=0.4); domain no match (weight=0.3)",
        }),
      ),
    ).toBe(false);
  });

  it("is false when fitExplanation is null (unscored)", () => {
    expect(isExcludedOpportunity(opportunity({ opportunityId: "a", fitExplanation: null }))).toBe(false);
  });

  it("is false when 'excluded' appears mid-string rather than as a prefix", () => {
    expect(
      isExcludedOpportunity(
        opportunity({ opportunityId: "a", fitExplanation: "role_family matched; not excluded by any rule" }),
      ),
    ).toBe(false);
  });
});

describe("compareOpportunitiesByScoreDescNullsLast", () => {
  it("orders higher score first", () => {
    expect(compareOpportunitiesByScoreDescNullsLast({ fitScore: 80 }, { fitScore: 40 })).toBeLessThan(0);
  });

  it("treats null as strictly last, never as 0", () => {
    expect(compareOpportunitiesByScoreDescNullsLast({ fitScore: null }, { fitScore: 0 })).toBeGreaterThan(0);
    expect(compareOpportunitiesByScoreDescNullsLast({ fitScore: 0 }, { fitScore: null })).toBeLessThan(0);
  });

  it("is 0 for two equal scores and for two nulls", () => {
    expect(compareOpportunitiesByScoreDescNullsLast({ fitScore: 50 }, { fitScore: 50 })).toBe(0);
    expect(compareOpportunitiesByScoreDescNullsLast({ fitScore: null }, { fitScore: null })).toBe(0);
  });
});

describe("rankOpportunitiesByScore", () => {
  it("sorts descending by score", () => {
    const low = opportunity({ opportunityId: "low", fitScore: 20 });
    const high = opportunity({ opportunityId: "high", fitScore: 90 });
    const mid = opportunity({ opportunityId: "mid", fitScore: 55 });
    expect(rankOpportunitiesByScore([low, high, mid]).map((o) => o.opportunityId)).toEqual([
      "high",
      "mid",
      "low",
    ]);
  });

  it("puts nulls last without treating them as 0", () => {
    const zero = opportunity({ opportunityId: "zero", fitScore: 0 });
    const unscored = opportunity({ opportunityId: "unscored", fitScore: null });
    const scored = opportunity({ opportunityId: "scored", fitScore: 10 });
    expect(rankOpportunitiesByScore([unscored, zero, scored]).map((o) => o.opportunityId)).toEqual([
      "scored",
      "zero",
      "unscored",
    ]);
  });

  it("is stable on ties and does not mutate the input array", () => {
    const a = opportunity({ opportunityId: "a", fitScore: 50 });
    const b = opportunity({ opportunityId: "b", fitScore: 50 });
    const input = [a, b];
    const ranked = rankOpportunitiesByScore(input);
    expect(ranked.map((o) => o.opportunityId)).toEqual(["a", "b"]);
    expect(input).toEqual([a, b]);
    expect(ranked).not.toBe(input);
  });

  it("returns an empty array for an empty input, never throws", () => {
    expect(rankOpportunitiesByScore([])).toEqual([]);
  });
});

describe("partitionOpportunitiesForList (Lane G item 1)", () => {
  it("splits into scored (ranked desc), unscored, and excluded groups", () => {
    const scoredLow = opportunity({ opportunityId: "scored-low", fitScore: 30 });
    const scoredHigh = opportunity({ opportunityId: "scored-high", fitScore: 95 });
    const unscoredA = opportunity({ opportunityId: "unscored-a", fitScore: null });
    const unscoredB = opportunity({ opportunityId: "unscored-b", fitScore: null });
    const excludedA = opportunity({
      opportunityId: "excluded-a",
      fitScore: 0,
      fitExplanation: "excluded: current employer",
    });

    const result = partitionOpportunitiesForList([
      unscoredA,
      excludedA,
      scoredLow,
      unscoredB,
      scoredHigh,
    ]);

    expect(result.scored.map((o) => o.opportunityId)).toEqual(["scored-high", "scored-low"]);
    expect(result.unscored.map((o) => o.opportunityId)).toEqual(["unscored-a", "unscored-b"]);
    expect(result.excluded.map((o) => o.opportunityId)).toEqual(["excluded-a"]);
  });

  it("never lets a 0-scored excluded opportunity leak into the scored group", () => {
    const excluded = opportunity({
      opportunityId: "excluded",
      fitScore: 0,
      fitExplanation: "excluded: employer in exclusions (current employer) — 'IntelePeer' matches 'IntelePeer'",
    });
    const result = partitionOpportunitiesForList([excluded]);
    expect(result.scored).toEqual([]);
    expect(result.unscored).toEqual([]);
    expect(result.excluded.map((o) => o.opportunityId)).toEqual(["excluded"]);
  });

  it("never lets a genuinely 0-scored, non-excluded opportunity leak into excluded", () => {
    const genuineZero = opportunity({
      opportunityId: "genuine-zero",
      fitScore: 0,
      fitExplanation: "role_family no match (weight=0.4)",
    });
    const result = partitionOpportunitiesForList([genuineZero]);
    expect(result.excluded).toEqual([]);
    expect(result.scored.map((o) => o.opportunityId)).toEqual(["genuine-zero"]);
  });

  it("preserves input order within the unscored and excluded groups", () => {
    const u1 = opportunity({ opportunityId: "u1", fitScore: null });
    const u2 = opportunity({ opportunityId: "u2", fitScore: null });
    const e1 = opportunity({ opportunityId: "e1", fitScore: 0, fitExplanation: "excluded: a" });
    const e2 = opportunity({ opportunityId: "e2", fitScore: 0, fitExplanation: "excluded: b" });
    const result = partitionOpportunitiesForList([u2, e2, u1, e1]);
    expect(result.unscored.map((o) => o.opportunityId)).toEqual(["u2", "u1"]);
    expect(result.excluded.map((o) => o.opportunityId)).toEqual(["e2", "e1"]);
  });

  it("returns three empty groups for an empty input", () => {
    const result = partitionOpportunitiesForList([]);
    expect(result).toEqual({ scored: [], unscored: [], excluded: [] });
  });

  it("does not mutate the input array", () => {
    const a = opportunity({ opportunityId: "a", fitScore: 10 });
    const b = opportunity({ opportunityId: "b", fitScore: 90 });
    const input = [a, b];
    partitionOpportunitiesForList(input);
    expect(input).toEqual([a, b]);
  });
});
