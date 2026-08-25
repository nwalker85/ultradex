import type { Relationship } from "@ultradex/sdk";

export function relevanceScoreTone(
  score: number | null | undefined,
): "success" | "accent" | "warning" | "neutral" {
  if (score === null || score === undefined) return "neutral";
  if (score >= 80) return "success";
  if (score >= 60) return "accent";
  if (score >= 40) return "warning";
  return "neutral";
}

export function filterRelationships(
  relationships: readonly Relationship[],
  query: string,
): Relationship[] {
  if (!query.trim()) return [...relationships];
  const q = query.toLowerCase().trim();
  return relationships.filter((rel) => {
    const matchContact = rel.dexContactRef.toLowerCase().includes(q);
    const matchOpportunity = rel.opportunityId.toLowerCase().includes(q);
    const matchSummary = rel.relevanceSummary?.toLowerCase().includes(q) ?? false;
    return matchContact || matchOpportunity || matchSummary;
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
    description: "No relationship mappings matched your search query. Reset filter to view all connections.",
  };
}
