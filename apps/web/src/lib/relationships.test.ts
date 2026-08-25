import { describe, expect, it } from "vitest";
import type { Relationship } from "@ultradex/sdk";

import {
  filterRelationships,
  relationshipsEmptyState,
  relevanceScoreTone,
} from "./relationships.js";

const sampleRelationships: Relationship[] = [
  {
    relationshipId: "rel-1",
    opportunityId: "opp-1",
    dexContactRef: "dex:contact-1",
    relevanceScore: 95.0,
    relevanceSummary: "Sarah Chen is VP of Research at Anthropic.",
    freshness: null,
    createdAt: "2026-08-20T10:00:00Z",
    updatedAt: "2026-08-20T10:00:00Z",
  },
  {
    relationshipId: "rel-2",
    opportunityId: "opp-2",
    dexContactRef: "dex:contact-2",
    relevanceScore: 70.0,
    relevanceSummary: "Alex Miller is Head of Talent at Deepgram.",
    freshness: null,
    createdAt: "2026-08-21T10:00:00Z",
    updatedAt: "2026-08-21T10:00:00Z",
  },
];

describe("relationships helper module", () => {
  it("determines relevance score tones correctly", () => {
    expect(relevanceScoreTone(95)).toBe("success");
    expect(relevanceScoreTone(70)).toBe("accent");
    expect(relevanceScoreTone(50)).toBe("warning");
    expect(relevanceScoreTone(30)).toBe("neutral");
    expect(relevanceScoreTone(null)).toBe("neutral");
  });

  it("filters relationships by search query across contact ref, opp ID, and summary", () => {
    const sarah = filterRelationships(sampleRelationships, "Sarah");
    expect(sarah).toHaveLength(1);
    expect(sarah[0]?.relationshipId).toBe("rel-1");

    const opp2 = filterRelationships(sampleRelationships, "opp-2");
    expect(opp2).toHaveLength(1);
    expect(opp2[0]?.relationshipId).toBe("rel-2");

    const none = filterRelationships(sampleRelationships, "nonexistent");
    expect(none).toHaveLength(0);
  });

  it("generates correct empty states", () => {
    expect(relationshipsEmptyState(false).title).toBe("No relationships mapped");
    expect(relationshipsEmptyState(true).title).toBe("No matching relationships");
  });
});
