import type { Lead, LeadConvertParameters, LeadStatus } from "@ultradex/sdk";

export const LEAD_STATUS_FILTERS = [
  "discovered",
  "unapplied",
  "converted",
  "dismissed",
] as const;

export type LeadStatusFilter = "" | (typeof LEAD_STATUS_FILTERS)[number];

export interface LeadsEmptyState {
  readonly title: string;
  readonly description: string;
}

export interface LeadFilterCriteria {
  readonly status?: LeadStatusFilter;
  readonly minFitScore?: number | null;
  readonly search?: string;
}

export function leadsEmptyState(filter: LeadStatusFilter): LeadsEmptyState {
  if (filter === "") {
    return {
      title: "No job leads found",
      description:
        "Sense career boards via the dynamic sourcing engine to ingest and score new opportunities.",
    };
  }
  return {
    title: `No leads with status "${filter}"`,
    description: `No job leads currently match the status filter "${filter}". Reset the filter to view all discovered postings.`,
  };
}

export function formatFitScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "—";
  }
  return `${Math.round(score)}%`;
}

export function fitScoreTone(
  score: number | null | undefined,
): "success" | "accent" | "warning" | "neutral" {
  if (score === null || score === undefined) return "neutral";
  if (score >= 85) return "success";
  if (score >= 70) return "accent";
  if (score >= 50) return "warning";
  return "neutral";
}

export function filterLeads(
  leads: readonly Lead[],
  criteria: LeadFilterCriteria,
): Lead[] {
  let filtered = [...leads];

  if (criteria.status && criteria.status !== "") {
    filtered = filtered.filter((lead) => lead.state === criteria.status);
  }

  if (
    criteria.minFitScore !== undefined &&
    criteria.minFitScore !== null &&
    criteria.minFitScore > 0
  ) {
    filtered = filtered.filter(
      (lead) =>
        lead.fitScore !== null && lead.fitScore >= (criteria.minFitScore ?? 0),
    );
  }

  if (criteria.search && criteria.search.trim() !== "") {
    const q = criteria.search.toLowerCase().trim();
    filtered = filtered.filter((lead) => {
      const matchEmployer = lead.employer.toLowerCase().includes(q);
      const matchTitle = lead.title.toLowerCase().includes(q);
      const matchSource = lead.sourceBoard.toLowerCase().includes(q);
      const matchLocation = lead.location?.toLowerCase().includes(q) ?? false;
      const matchRequirements = lead.requirements.some((r) =>
        r.toLowerCase().includes(q),
      );
      return (
        matchEmployer ||
        matchTitle ||
        matchSource ||
        matchLocation ||
        matchRequirements
      );
    });
  }

  return filtered;
}

export function buildLeadConvertParameters(
  lead: Lead,
  overrides?: Partial<LeadConvertParameters>,
): LeadConvertParameters {
  return {
    leadId: lead.id,
    customTitle: overrides?.customTitle ?? `${lead.employer} — ${lead.title}`,
    stage: overrides?.stage ?? "applied",
    occurredAt: overrides?.occurredAt ?? new Date().toISOString(),
    contactRefs: overrides?.contactRefs ?? [],
    nextAction: overrides?.nextAction ?? "Review application receipt & follow up",
    targetRoleFamily: overrides?.targetRoleFamily,
    nextActionDeadline: overrides?.nextActionDeadline,
  };
}

export function findLeadById(
  leads: readonly Lead[],
  id: string,
): Lead | null {
  return leads.find((l) => l.id === id) ?? null;
}
