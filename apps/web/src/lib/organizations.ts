import type { Organization } from "@ultradex/sdk";

export type OrganizationSortField = "name" | "advocacy" | "size";

export interface OrganizationsEmptyState {
  readonly title: string;
  readonly description: string;
}

export function organizationsEmptyState(search: string): OrganizationsEmptyState {
  if (!search.trim()) {
    return {
      title: "No organizations recorded",
      description: "Add an employer directory record or ingest leads to auto-populate organizations.",
    };
  }
  return {
    title: `No organizations matching "${search}"`,
    description: `No employers matched your search query "${search}". Clear search to view all organizations.`,
  };
}

export function formatAdvocacyRating(rating: number | null | undefined): string {
  if (rating === null || rating === undefined || Number.isNaN(rating)) {
    return "—";
  }
  return `${Math.round(rating)}%`;
}

export function advocacyTone(
  rating: number | null | undefined,
): "success" | "accent" | "warning" | "neutral" {
  if (rating === null || rating === undefined) return "neutral";
  if (rating >= 80) return "success";
  if (rating >= 60) return "accent";
  if (rating >= 40) return "warning";
  return "neutral";
}

export function sortOrganizations(
  orgs: readonly Organization[],
  sortBy: OrganizationSortField,
): Organization[] {
  const sorted = [...orgs];
  if (sortBy === "name") {
    return sorted.sort((a, b) => a.name.localeCompare(b.name));
  }
  if (sortBy === "advocacy") {
    return sorted.sort((a, b) => (b.advocacyRating ?? -1) - (a.advocacyRating ?? -1));
  }
  if (sortBy === "size") {
    return sorted.sort((a, b) => (a.size ?? "").localeCompare(b.size ?? ""));
  }
  return sorted;
}

export function filterOrganizations(
  orgs: readonly Organization[],
  search: string,
): Organization[] {
  if (!search.trim()) return [...orgs];
  const q = search.toLowerCase().trim();
  return orgs.filter((org) => {
    const matchName = org.name.toLowerCase().includes(q);
    const matchDomain = org.domain?.toLowerCase().includes(q) ?? false;
    const matchIndustry = org.industry?.toLowerCase().includes(q) ?? false;
    const matchNotes = org.notes?.toLowerCase().includes(q) ?? false;
    return matchName || matchDomain || matchIndustry || matchNotes;
  });
}

export function findOrganizationById(
  orgs: readonly Organization[],
  id: string,
): Organization | null {
  return orgs.find((o) => o.id === id) ?? null;
}
