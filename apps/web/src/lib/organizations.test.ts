import { describe, expect, it } from "vitest";
import type { Organization } from "@ultradex/sdk";

import {
  advocacyTone,
  filterOrganizations,
  findOrganizationById,
  formatAdvocacyRating,
  organizationsEmptyState,
  sortOrganizations,
} from "./organizations.js";

const sampleOrgs: Organization[] = [
  {
    id: "org-1",
    name: "Anthropic",
    domain: "anthropic.com",
    industry: "AI Research & Frontier Models",
    size: "500-1000",
    advocacyRating: 92.0,
    notes: "Top-tier AI lab. Strong internal champions in research.",
    createdAt: "2026-08-20T10:00:00Z",
    updatedAt: "2026-08-20T10:00:00Z",
  },
  {
    id: "org-2",
    name: "Deepgram",
    domain: "deepgram.com",
    industry: "Speech AI & Voice Infrastructure",
    size: "100-250",
    advocacyRating: 78.5,
    notes: "Speech-to-text platform with modern API architecture.",
    createdAt: "2026-08-21T10:00:00Z",
    updatedAt: "2026-08-21T10:00:00Z",
  },
  {
    id: "org-3",
    name: "SoundHound",
    domain: "soundhound.com",
    industry: "Voice AI & Telephony",
    size: "1000+",
    advocacyRating: 45.0,
    notes: "Legacy voice AI platform.",
    createdAt: "2026-08-22T10:00:00Z",
    updatedAt: "2026-08-22T10:00:00Z",
  },
];

describe("organizations helper module", () => {
  it("formats advocacy rating correctly", () => {
    expect(formatAdvocacyRating(92.0)).toBe("92%");
    expect(formatAdvocacyRating(78.5)).toBe("79%");
    expect(formatAdvocacyRating(null)).toBe("—");
    expect(formatAdvocacyRating(undefined)).toBe("—");
    expect(formatAdvocacyRating(NaN)).toBe("—");
  });

  it("determines advocacy tone correctly", () => {
    expect(advocacyTone(90)).toBe("success");
    expect(advocacyTone(80)).toBe("success");
    expect(advocacyTone(70)).toBe("accent");
    expect(advocacyTone(50)).toBe("warning");
    expect(advocacyTone(30)).toBe("neutral");
    expect(advocacyTone(null)).toBe("neutral");
  });

  it("generates correct empty states for search and blank queries", () => {
    const emptyDefault = organizationsEmptyState("");
    expect(emptyDefault.title).toBe("No organizations recorded");

    const emptySearch = organizationsEmptyState("Google");
    expect(emptySearch.title).toBe('No organizations matching "Google"');
    expect(emptySearch.description).toContain("Google");
  });

  it("sorts organizations by name, advocacy rating, and size", () => {
    const byName = sortOrganizations(sampleOrgs, "name");
    expect(byName.map((o) => o.name)).toEqual(["Anthropic", "Deepgram", "SoundHound"]);

    const byAdvocacy = sortOrganizations(sampleOrgs, "advocacy");
    expect(byAdvocacy.map((o) => o.name)).toEqual(["Anthropic", "Deepgram", "SoundHound"]);

    const bySize = sortOrganizations(sampleOrgs, "size");
    expect(bySize.length).toBe(3);
  });

  it("filters organizations by text query across name, domain, industry, and notes", () => {
    const speech = filterOrganizations(sampleOrgs, "speech");
    expect(speech).toHaveLength(1);
    expect(speech[0]?.name).toBe("Deepgram");

    const domainSearch = filterOrganizations(sampleOrgs, "anthropic.com");
    expect(domainSearch).toHaveLength(1);
    expect(domainSearch[0]?.name).toBe("Anthropic");

    const none = filterOrganizations(sampleOrgs, "nonexistent");
    expect(none).toHaveLength(0);
  });

  it("finds organization by ID", () => {
    expect(findOrganizationById(sampleOrgs, "org-2")?.name).toBe("Deepgram");
    expect(findOrganizationById(sampleOrgs, "invalid")).toBeNull();
  });
});
