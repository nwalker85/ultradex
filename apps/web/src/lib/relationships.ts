import type { Contact, Opportunity, Relationship } from "@ultradex/sdk";

/** Strip Dex ref prefix to local ContactDB id (`dex-{uuid}` → `{uuid}`). */
export function dexRefToContactId(dexContactRef: string): string {
  return dexContactRef.replace(/^dex[-:]/, "").replace(/^contact-/, "");
}

export interface ParsedRelevanceSummary {
  readonly name: string | null;
  readonly role: string | null;
  readonly organization: string | null;
}

/** Best-effort parse of relationship relevance text when contact join misses. */
export function parseRelevanceSummary(
  summary: string | null | undefined,
): ParsedRelevanceSummary {
  if (!summary?.trim()) {
    return { name: null, role: null, organization: null };
  }
  const text = summary.trim();
  const parenAt = /^(.+?) \((.+?)\) at (.+)$/.exec(text);
  if (parenAt) {
    return {
      name: parenAt[1]!.trim(),
      role: parenAt[2]!.trim(),
      organization: parenAt[3]!.trim(),
    };
  }
  const isAt = /^(.+?) is (.+?) at (.+?)\.?$/.exec(text);
  if (isAt) {
    return {
      name: isAt[1]!.trim(),
      role: isAt[2]!.trim(),
      organization: isAt[3]!.trim(),
    };
  }
  const parenOnly = /^(.+?) \((.+?)\)$/.exec(text);
  if (parenOnly) {
    return {
      name: parenOnly[1]!.trim(),
      role: parenOnly[2]!.trim(),
      organization: null,
    };
  }
  return { name: text, role: null, organization: null };
}

export interface RelationshipDisplay {
  readonly relationship: Relationship;
  readonly contact: Contact | null;
  readonly opportunity: Opportunity | null;
  readonly name: string;
  readonly organization: string | null;
  readonly role: string | null;
}

export function buildRelationshipDisplay(
  relationship: Relationship,
  contact: Contact | null,
  opportunity: Opportunity | null,
): RelationshipDisplay {
  const parsed = parseRelevanceSummary(relationship.relevanceSummary);
  return {
    relationship,
    contact,
    opportunity,
    name: contact?.name ?? parsed.name ?? relationship.dexContactRef,
    organization: contact?.company ?? parsed.organization ?? opportunity?.employer ?? null,
    role: contact?.jobTitle ?? parsed.role ?? null,
  };
}

export function findRelationshipById(
  relationships: readonly Relationship[],
  id: string,
): Relationship | null {
  return relationships.find((rel) => rel.relationshipId === id) ?? null;
}

export function relevanceScoreTone(
  score: number | null | undefined,
): "success" | "accent" | "warning" | "neutral" {
  if (score === null || score === undefined) return "neutral";
  if (score >= 80) return "success";
  if (score >= 60) return "accent";
  if (score >= 40) return "warning";
  return "neutral";
}


export function dedupeRelationshipDisplaysByContact(
  rows: readonly RelationshipDisplay[],
): RelationshipDisplay[] {
  const best = new Map<string, RelationshipDisplay>();
  for (const row of rows) {
    const key = row.relationship.dexContactRef;
    const existing = best.get(key);
    if (existing === undefined) {
      best.set(key, row);
      continue;
    }
    const rowScore = row.relationship.relevanceScore ?? -1;
    const existingScore = existing.relationship.relevanceScore ?? -1;
    if (rowScore > existingScore) {
      best.set(key, row);
    }
  }
  return [...best.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export function filterRelationshipDisplays(
  rows: readonly RelationshipDisplay[],
  query: string,
): RelationshipDisplay[] {
  if (!query.trim()) return [...rows];
  const q = query.toLowerCase().trim();
  return rows.filter((row) => {
    const matchName = row.name.toLowerCase().includes(q);
    const matchOrg = row.organization?.toLowerCase().includes(q) ?? false;
    const matchRole = row.role?.toLowerCase().includes(q) ?? false;
    const matchOpportunity = row.relationship.opportunityId.toLowerCase().includes(q);
    const matchSummary =
      row.relationship.relevanceSummary?.toLowerCase().includes(q) ?? false;
    return matchName || matchOrg || matchRole || matchOpportunity || matchSummary;
  });
}

/** @deprecated Use filterRelationshipDisplays for enriched rows. */
export function filterRelationships(
  relationships: readonly Relationship[],
  query: string,
): Relationship[] {
  if (!query.trim()) return [...relationships];
  const q = query.toLowerCase().trim();
  return relationships.filter((rel) => {
    const parsed = parseRelevanceSummary(rel.relevanceSummary);
    const matchContact = rel.dexContactRef.toLowerCase().includes(q);
    const matchOpportunity = rel.opportunityId.toLowerCase().includes(q);
    const matchSummary = rel.relevanceSummary?.toLowerCase().includes(q) ?? false;
    const matchName = parsed.name?.toLowerCase().includes(q) ?? false;
    const matchOrg = parsed.organization?.toLowerCase().includes(q) ?? false;
    const matchRole = parsed.role?.toLowerCase().includes(q) ?? false;
    return (
      matchContact ||
      matchOpportunity ||
      matchSummary ||
      matchName ||
      matchOrg ||
      matchRole
    );
  });
}

export function relationshipsEmptyState(hasFilter: boolean): {
  title: string;
  description: string;
} {
  if (!hasFilter) {
    return {
      title: "No relationships mapped",
      description: "Sync Dex contacts to pipeline opportunities from the Opportunity dossier.",
    };
  }
  return {
    title: "No matching relationships",
    description:
      "No relationship mappings matched your search query. Reset filter to view all connections.",
  };
}
