import { describe, expect, it } from "vitest";
import type { CommunicationEntry, Contact } from "@ultradex/sdk";

import {
  contactsEmptyState,
  filterContacts,
  findContactById,
  isNeglectedContact,
  relationshipTierTone,
  sortCommunicationHistoryDesc,
} from "./contacts.js";

const sampleContacts: Contact[] = [
  {
    id: "dex:contact-1",
    name: "Sarah Chen",
    email: "sarah.chen@anthropic.com",
    company: "Anthropic",
    jobTitle: "VP of Research",
    phone: "+1 555 0192",
    notes: "Key executive advocate in distributed agentic reasoning.",
    lastContacted: "2026-06-01T12:00:00Z", // >60 days ago
    aiValue: 92.0,
    aiReason: "High internal influence at top target employer.",
    outreachStrategy: "Warm reconnect discussing frontier multi-agent evaluation.",
    suggestedTiming: "Immediate",
    lastAnalyzed: "2026-08-20T12:00:00Z",
    advocacyScore: 90.0,
    organizationId: "org-1",
    crmNotes: "Discussed CTO and AI Architect roles.",
    communicationHistory: [
      {
        id: "comm-1",
        timestamp: "2026-06-01T12:00:00Z",
        channel: "gmail",
        direction: "outbound",
        subject: "Re: Agentic Infrastructure Deep Dive",
        summary: "Sent briefing on LLM tool sandboxing.",
      },
      {
        id: "comm-2",
        timestamp: "2026-05-15T10:00:00Z",
        channel: "linkedin",
        direction: "inbound",
        subject: "Great to connect",
        summary: "Introductory outreach from Sarah.",
      },
    ],
    linkedinUrl: "https://linkedin.com/in/sarahchen",
    relationshipTier: "champion",
    createdAt: "2026-01-15T00:00:00Z",
    updatedAt: "2026-08-20T00:00:00Z",
  },
  {
    id: "dex:contact-2",
    name: "Alex Miller",
    email: "alex@deepgram.com",
    company: "Deepgram",
    jobTitle: "Head of Talent",
    phone: null,
    notes: "Inbound recruiter for Voice AI leadership role.",
    lastContacted: "2026-08-22T10:00:00Z", // recent (<30 days)
    aiValue: 70.0,
    aiReason: "Active recruiter sourcing for VP Voice AI.",
    outreachStrategy: "Send 3-pill availability with open GCal slots.",
    suggestedTiming: "Within 24h",
    lastAnalyzed: "2026-08-22T10:00:00Z",
    advocacyScore: 65.0,
    organizationId: "org-2",
    crmNotes: null,
    communicationHistory: [],
    linkedinUrl: "https://linkedin.com/in/alexmiller",
    relationshipTier: "recruiter",
    createdAt: "2026-08-22T00:00:00Z",
    updatedAt: "2026-08-22T00:00:00Z",
  },
  {
    id: "dex:contact-3",
    name: "David Kim",
    email: "david@startup.io",
    company: "Stealth AI",
    jobTitle: "Co-Founder",
    phone: null,
    notes: "Met at conference.",
    lastContacted: null,
    aiValue: 40.0,
    aiReason: null,
    outreachStrategy: null,
    suggestedTiming: null,
    lastAnalyzed: null,
    advocacyScore: 30.0,
    organizationId: null,
    crmNotes: null,
    communicationHistory: [],
    linkedinUrl: null,
    relationshipTier: "peer",
    createdAt: "2026-02-01T00:00:00Z",
    updatedAt: "2026-02-01T00:00:00Z",
  },
];

describe("contacts helper module", () => {
  const referenceNow = new Date("2026-08-24T12:00:00Z");

  it("identifies neglected contacts correctly based on aiValue >= 60 and >30 days inactivity", () => {
    expect(isNeglectedContact(sampleContacts[0]!, referenceNow)).toBe(true);
    expect(isNeglectedContact(sampleContacts[1]!, referenceNow)).toBe(false); // recent contact
    expect(isNeglectedContact(sampleContacts[2]!, referenceNow)).toBe(false); // low aiValue (<60)
  });

  it("maps relationship tiers to visual tones", () => {
    expect(relationshipTierTone("champion")).toBe("success");
    expect(relationshipTierTone("advocate")).toBe("accent");
    expect(relationshipTierTone("recruiter")).toBe("warning");
    expect(relationshipTierTone("peer")).toBe("neutral");
    expect(relationshipTierTone(null)).toBe("neutral");
  });

  it("filters contacts by search string across name, company, title, email, notes", () => {
    const sarah = filterContacts(sampleContacts, { search: "sarah" });
    expect(sarah).toHaveLength(1);
    expect(sarah[0]?.name).toBe("Sarah Chen");

    const vpSearch = filterContacts(sampleContacts, { search: "VP of Research" });
    expect(vpSearch).toHaveLength(1);
    expect(vpSearch[0]?.id).toBe("dex:contact-1");

    const deepgram = filterContacts(sampleContacts, { search: "deepgram" });
    expect(deepgram).toHaveLength(1);
    expect(deepgram[0]?.name).toBe("Alex Miller");
  });

  it("filters contacts by relationship tier", () => {
    const champions = filterContacts(sampleContacts, { tier: "champion" });
    expect(champions).toHaveLength(1);
    expect(champions[0]?.name).toBe("Sarah Chen");

    const recruiters = filterContacts(sampleContacts, { tier: "recruiter" });
    expect(recruiters).toHaveLength(1);
    expect(recruiters[0]?.name).toBe("Alex Miller");
  });

  it("filters contacts by min advocacy score", () => {
    const highAdvocacy = filterContacts(sampleContacts, { minAdvocacyScore: 80 });
    expect(highAdvocacy).toHaveLength(1);
    expect(highAdvocacy[0]?.name).toBe("Sarah Chen");
  });

  it("filters contacts by onlyNeglected flag", () => {
    const neglected = filterContacts(sampleContacts, { onlyNeglected: true });
    expect(neglected).toHaveLength(1);
    expect(neglected[0]?.name).toBe("Sarah Chen");
  });

  it("sorts communication history in descending chronological order", () => {
    const history: CommunicationEntry[] = sampleContacts[0]!.communicationHistory;
    const sorted = sortCommunicationHistoryDesc(history);
    expect(sorted[0]?.id).toBe("comm-1"); // 2026-06-01
    expect(sorted[1]?.id).toBe("comm-2"); // 2026-05-15
  });

  it("generates correct empty states for filtered and non-filtered states", () => {
    expect(contactsEmptyState({}).title).toBe("No contacts found");
    expect(contactsEmptyState({ search: "Nobody" }).title).toBe("No matching contacts");
  });

  it("finds contact by ID or returns null", () => {
    expect(findContactById(sampleContacts, "dex:contact-1")?.name).toBe("Sarah Chen");
    expect(findContactById(sampleContacts, "unknown")).toBeNull();
  });
});
