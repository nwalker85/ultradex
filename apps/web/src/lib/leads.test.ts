import { describe, expect, it } from "vitest";
import type { Lead } from "@ultradex/sdk";

import {
  buildLeadConvertParameters,
  filterLeads,
  findLeadById,
  fitScoreTone,
  formatFitScore,
  leadsEmptyState,
} from "./leads.js";

const sampleLeads: Lead[] = [
  {
    id: "lead-1",
    employer: "Anthropic",
    title: "Head of AI Platform Architecture",
    sourceBoard: "anthropic",
    externalId: "ext-1",
    organizationId: "org-1",
    location: "San Francisco, CA / Remote",
    remoteType: "remote",
    salaryMin: 220000,
    salaryMax: 300000,
    salaryCurrency: "USD",
    url: "https://anthropic.com/careers/head-ai",
    description: "Lead agentic AI systems and distributed infrastructure.",
    requirements: ["LLM Systems", "Kubernetes", "Python", "Rust"],
    fitScore: 94.5,
    matchBreakdown: { skills: 95, domain: 92 },
    riskFlags: [],
    state: "discovered",
    convertedOpportunityId: null,
    createdAt: "2026-08-20T10:00:00Z",
    updatedAt: "2026-08-20T10:00:00Z",
  },
  {
    id: "lead-2",
    employer: "Parloa",
    title: "VP of Engineering & Conversational AI",
    sourceBoard: "parloa",
    externalId: "ext-2",
    organizationId: "org-2",
    location: "New York, NY / Hybrid",
    remoteType: "hybrid",
    salaryMin: 200000,
    salaryMax: 270000,
    salaryCurrency: "USD",
    url: "https://parloa.com/careers/vp-eng",
    description: "Lead enterprise voice and conversational AI platforms.",
    requirements: ["Voice AI", "ASR/TTS", "Engineering Leadership"],
    fitScore: 88.0,
    matchBreakdown: { skills: 90, domain: 85 },
    riskFlags: ["hybrid_relocation"],
    state: "unapplied",
    convertedOpportunityId: null,
    createdAt: "2026-08-21T10:00:00Z",
    updatedAt: "2026-08-21T10:00:00Z",
  },
  {
    id: "lead-3",
    employer: "SoundHound",
    title: "Senior Telephony Engineer",
    sourceBoard: "soundhound",
    externalId: "ext-3",
    organizationId: "org-3",
    location: "Austin, TX",
    remoteType: "onsite",
    salaryMin: 150000,
    salaryMax: 175000,
    salaryCurrency: "USD",
    url: "https://soundhound.com/careers/telephony",
    description: "Telephony gateway engineer.",
    requirements: ["SIP", "FreeSWITCH", "C++"],
    fitScore: 58.0,
    matchBreakdown: { skills: 60, domain: 55 },
    riskFlags: ["below_comp_floor", "onsite_required"],
    state: "dismissed",
    convertedOpportunityId: null,
    createdAt: "2026-08-22T10:00:00Z",
    updatedAt: "2026-08-22T10:00:00Z",
  },
  {
    id: "lead-4",
    employer: "OpenAI",
    title: "Principal Solutions Architect",
    sourceBoard: "openai",
    externalId: "ext-4",
    organizationId: "org-4",
    location: "Remote",
    remoteType: "remote",
    salaryMin: 240000,
    salaryMax: 320000,
    salaryCurrency: "USD",
    url: "https://openai.com/careers/principal-sa",
    description: "Enterprise customer solutions for frontier models.",
    requirements: ["Enterprise Architecture", "LLM Systems", "FastAPI"],
    fitScore: 92.0,
    matchBreakdown: { skills: 94, domain: 90 },
    riskFlags: [],
    state: "converted",
    convertedOpportunityId: "opp-4",
    createdAt: "2026-08-23T10:00:00Z",
    updatedAt: "2026-08-23T10:00:00Z",
  },
];

describe("leads helper module", () => {
  it("formats fit score correctly", () => {
    expect(formatFitScore(94.5)).toBe("95%");
    expect(formatFitScore(88)).toBe("88%");
    expect(formatFitScore(0)).toBe("0%");
    expect(formatFitScore(null)).toBe("—");
    expect(formatFitScore(undefined)).toBe("—");
    expect(formatFitScore(NaN)).toBe("—");
  });

  it("determines fit score tone correctly", () => {
    expect(fitScoreTone(95)).toBe("success");
    expect(fitScoreTone(85)).toBe("success");
    expect(fitScoreTone(75)).toBe("accent");
    expect(fitScoreTone(60)).toBe("warning");
    expect(fitScoreTone(45)).toBe("neutral");
    expect(fitScoreTone(null)).toBe("neutral");
  });

  it("provides informative empty states for all filters", () => {
    const emptyAll = leadsEmptyState("");
    expect(emptyAll.title).toBe("No job leads found");
    expect(emptyAll.description).toContain("Sense career boards");

    const emptyDiscovered = leadsEmptyState("discovered");
    expect(emptyDiscovered.title).toBe('No leads with status "discovered"');
    expect(emptyDiscovered.description).toContain("Reset the filter");
  });

  it("filters leads by status", () => {
    const discovered = filterLeads(sampleLeads, { status: "discovered" });
    expect(discovered).toHaveLength(1);
    expect(discovered[0]?.employer).toBe("Anthropic");

    const converted = filterLeads(sampleLeads, { status: "converted" });
    expect(converted).toHaveLength(1);
    expect(converted[0]?.employer).toBe("OpenAI");
  });

  it("filters leads by minFitScore", () => {
    const highFit = filterLeads(sampleLeads, { minFitScore: 90 });
    expect(highFit).toHaveLength(2);
    expect(highFit.map((l) => l.employer)).toEqual(["Anthropic", "OpenAI"]);
  });

  it("filters leads by search query (case-insensitive over title, employer, requirements)", () => {
    const voiceLeads = filterLeads(sampleLeads, { search: "voice" });
    expect(voiceLeads).toHaveLength(1);
    expect(voiceLeads[0]?.employer).toBe("Parloa");

    const k8sLeads = filterLeads(sampleLeads, { search: "kubernetes" });
    expect(k8sLeads).toHaveLength(1);
    expect(k8sLeads[0]?.employer).toBe("Anthropic");

    const saLeads = filterLeads(sampleLeads, { search: "solutions architect" });
    expect(saLeads).toHaveLength(1);
    expect(saLeads[0]?.employer).toBe("OpenAI");
  });

  it("combines multiple filter criteria", () => {
    const combined = filterLeads(sampleLeads, {
      status: "discovered",
      minFitScore: 80,
      search: "anthropic",
    });
    expect(combined).toHaveLength(1);
    expect(combined[0]?.id).toBe("lead-1");
  });

  it("builds lead conversion parameters with defaults and overrides", () => {
    const lead = sampleLeads[0]!;
    const params = buildLeadConvertParameters(lead);

    expect(params.leadId).toBe("lead-1");
    expect(params.customTitle).toBe("Anthropic — Head of AI Platform Architecture");
    expect(params.stage).toBe("applied");
    expect(params.nextAction).toBe("Review application receipt & follow up");

    const overridden = buildLeadConvertParameters(lead, {
      customTitle: "Anthropic CTO Lead",
      stage: "screening",
      contactRefs: ["dex:contact-1"],
      targetRoleFamily: "Executive Engineering Leadership",
    });
    expect(overridden.customTitle).toBe("Anthropic CTO Lead");
    expect(overridden.stage).toBe("screening");
    expect(overridden.contactRefs).toEqual(["dex:contact-1"]);
    expect(overridden.targetRoleFamily).toBe("Executive Engineering Leadership");
  });

  it("finds lead by ID or returns null", () => {
    expect(findLeadById(sampleLeads, "lead-2")?.employer).toBe("Parloa");
    expect(findLeadById(sampleLeads, "non-existent")).toBeNull();
  });
});
