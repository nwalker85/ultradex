import { describe, expect, it } from "vitest";
import type { Contact, Relationship } from "@ultradex/sdk";

import {
  buildRelationshipDisplay,
  dexRefToContactId,
  filterRelationshipDisplays,
  filterRelationships,
  parseRelevanceSummary,
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

const sarahContact: Contact = {
  id: "contact-1",
  name: "Sarah Chen",
  email: "sarah@example.com",
  company: "Anthropic",
  jobTitle: "VP of Research",
  phone: null,
  notes: null,
  lastContacted: null,
  aiValue: null,
  aiReason: null,
  outreachStrategy: null,
  suggestedTiming: null,
  lastAnalyzed: null,
  advocacyScore: null,
  organizationId: null,
  crmNotes: null,
  communicationHistory: [],
  linkedinUrl: null,
  relationshipTier: "champion",
  createdAt: "2026-08-20T10:00:00Z",
  updatedAt: "2026-08-20T10:00:00Z",
};

describe("relationships helper module", () => {
  it("maps dex refs to contact ids", () => {
    expect(dexRefToContactId("dex-3ab184a2-303e-48f6-ba77-0721756a9dbd")).toBe(
      "3ab184a2-303e-48f6-ba77-0721756a9dbd",
    );
  });

  it("parses relevance summaries into name, role, and organization", () => {
    expect(parseRelevanceSummary("George Dekker (Owner) at Quant AI")).toEqual({
      name: "George Dekker",
      role: "Owner",
      organization: "Quant AI",
    });
  });

  it("builds display rows from contact data when available", () => {
    const row = buildRelationshipDisplay(sampleRelationships[0]!, sarahContact, null);
    expect(row.name).toBe("Sarah Chen");
    expect(row.organization).toBe("Anthropic");
    expect(row.role).toBe("VP of Research");
  });

  it("determines relevance score tones correctly", () => {
    expect(relevanceScoreTone(95)).toBe("success");
    expect(relevanceScoreTone(70)).toBe("accent");
    expect(relevanceScoreTone(50)).toBe("warning");
    expect(relevanceScoreTone(30)).toBe("neutral");
    expect(relevanceScoreTone(null)).toBe("neutral");
  });

  it("filters enriched rows by name and organization", () => {
    const rows = sampleRelationships.map((rel) =>
      buildRelationshipDisplay(
        rel,
        rel.relationshipId === "rel-1" ? sarahContact : null,
        null,
      ),
    );
    expect(filterRelationshipDisplays(rows, "Sarah")).toHaveLength(1);
    expect(filterRelationshipDisplays(rows, "Anthropic")).toHaveLength(1);
  });

  it("filters legacy relationship lists via parsed summary", () => {
    const sarah = filterRelationships(sampleRelationships, "Sarah");
    expect(sarah).toHaveLength(1);
    expect(sarah[0]?.relationshipId).toBe("rel-1");
  });

  it("generates correct empty states", () => {
    expect(relationshipsEmptyState(false).title).toBe("No relationships mapped");
    expect(relationshipsEmptyState(true).title).toBe("No matching relationships");
  });
});
