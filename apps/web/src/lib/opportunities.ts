import type { Opportunity } from "@ultradex/sdk";

/**
 * FR-OPP-1 — the 3 statuses ever offered as a filter. `archived` is
 * deliberately excluded: no command in this system ever writes it.
 */
export const OPPORTUNITY_STATUS_FILTERS = ["discovered", "qualified", "watching"] as const;

export type OpportunityStatusFilter = "" | (typeof OPPORTUNITY_STATUS_FILTERS)[number];

export interface OpportunitiesEmptyState {
  readonly title: string;
  readonly description: string;
  /** Whether "Clear filter" is the right recovery action (filtered-zero) vs "Create" (true-zero). */
  readonly kind: "true-zero" | "filtered-zero";
}

/**
 * FR-OPP-2 — two visibly different empty states. `filter === ""` (no status
 * filter applied) and zero results means the whole projection is empty
 * (true-zero: offer create). Any specific status filter yielding zero
 * results is a filtered-zero: the projection may well have rows in other
 * states, so the fix is to clear the filter, not create.
 */
export function opportunitiesEmptyState(filter: OpportunityStatusFilter): OpportunitiesEmptyState {
  if (filter === "") {
    return {
      title: "No opportunities yet",
      description: "Create the first opportunity from an evidence reference to get started.",
      kind: "true-zero",
    };
  }
  return {
    title: `No opportunities in ${filter}`,
    description: "Clear the filter to see opportunities in other states.",
    kind: "filtered-zero",
  };
}

/**
 * FR-OPP-3 — the SDK does not wrap the server's `opportunity(id)` field
 * (BE-1), so opportunity detail resolves by fetching a page and finding the
 * id client-side. This is a fallback that degrades past a few hundred rows
 * (NFR-1) — see the dev-mode warning in the detail route, which fires once
 * the backing list's `nextCursor` shows more rows exist than were fetched.
 */
export function findOpportunityById(
  items: readonly Opportunity[],
  id: string,
): Opportunity | null {
  return items.find((item) => item.opportunityId === id) ?? null;
}
