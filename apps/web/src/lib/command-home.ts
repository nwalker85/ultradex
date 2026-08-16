import type {
  Application,
  ApplicationPage,
  Operation,
  Opportunity,
  OpportunityPage,
  Outreach,
  OutreachPage,
  ProjectionFreshness,
  RelationshipPage,
} from "@ultradex/sdk";

import { isExcludedOpportunity, rankOpportunitiesByScore } from "./opportunity-ranking.js";

/**
 * Command home (`/`) roll-up logic — FR-CMD-1..5 (PRD §6.1). Kept as pure,
 * client-free functions so every rule here is unit-testable with synthetic
 * data, independent of the live Ultradex API (FR-CMD-4 exists precisely
 * because one of these rules is permanently unfireable against live data
 * today and must not silently vanish for lack of live rows).
 *
 * Command home fires five independent, mount-time loads: `listOpportunities`,
 * `listApplications`, `listOutreach`, `listOperations` — the primary SDK
 * bindings PRD §7's screen inventory names for the Command route, each
 * backing a rendered section — plus `listRelationships`, loaded ONLY for its
 * page-level freshness (supervisor decision 2026-08-15: Relationships is the
 * ~2242-contact projection the ambient Dex sweep feeds, and its staleness is
 * exactly what the freshness strip exists to surface). Relationships has no
 * rendered section on this page and contributes no rows to the Needs
 * Attention rail. `+page.svelte` fires all five independently and catches
 * each one's failure in isolation; this module never performs I/O.
 */

// ---------------------------------------------------------------------------
// FR-CMD-2 — freshness strip, 4 real projections only
// ---------------------------------------------------------------------------

/**
 * The system has exactly four real CQRS projections with genuine
 * page-level freshness metadata: Opportunity, Application, Relationship,
 * Outreach (see `sdk/typescript/src/contracts.ts` — `opportunityPageSchema`,
 * `applicationPageSchema`, `relationshipPageSchema`, `outreachPageSchema`
 * each carry a `freshness: ProjectionFreshness | null`). The strip covers
 * all four — Relationships is loaded with the smallest page the SDK allows
 * (`first: 1`) purely to read its freshness; Command home never renders a
 * Relationships section and never feeds a relationship row into the Needs
 * Attention rail (FR-CMD-3's ordering is unchanged).
 *
 * `Operation` is not a projection in this sense: `listOperations` returns a
 * bare array with no page-level freshness, and each `Operation.freshness`
 * field is hardcoded `null` server-side by design (PRD §4 governance
 * principle 4, `api/graphql/schema.py:102-104`). Structurally, this type
 * has no `operations` key at all — there is nothing to assign an
 * operation's freshness into, even by mistake.
 */
export interface CommandFreshnessInput {
  readonly opportunities: ProjectionFreshness | null;
  readonly applications: ProjectionFreshness | null;
  readonly relationships: ProjectionFreshness | null;
  readonly outreach: ProjectionFreshness | null;
}

/**
 * Builds the freshness rollup input from the raw section results loaded on
 * Command home. `operations` is accepted (Command home does load it, for
 * the Needs Attention rail — FR-CMD-3) but is never read here; this
 * function is the single seam a future change would have to touch to leak
 * `Operation.freshness` into the rollup, and the regression test in
 * `command-home.test.ts` pins that it never does.
 */
export function buildFreshnessRollupInput(bundle: {
  readonly opportunities: OpportunityPage | null;
  readonly applications: ApplicationPage | null;
  readonly relationships: RelationshipPage | null;
  readonly outreach: OutreachPage | null;
  readonly operations: readonly Operation[];
}): CommandFreshnessInput {
  return {
    opportunities: bundle.opportunities?.freshness ?? null,
    applications: bundle.applications?.freshness ?? null,
    relationships: bundle.relationships?.freshness ?? null,
    outreach: bundle.outreach?.freshness ?? null,
  };
}

/**
 * Worst-status-wins severity order, least to most severe. `fresh` is the
 * only status the live system produces today (governance principle 4), but
 * the ranking is written to degrade honestly the day one of these actually
 * falls behind — `unavailable` (no data at all) outranks `stale` (data,
 * but old), which outranks `replaying` (actively catching up) note: this is
 * a judgment call, since the PRD specifies "worst-status-wins" without
 * pinning an exact order; `unavailable` as the ceiling is the one part of
 * this ranking that is not a judgment call — it is strictly worse than
 * having any data at all.
 */
const FRESHNESS_SEVERITY: Record<ProjectionFreshness["status"], number> = {
  fresh: 0,
  replaying: 1,
  stale: 2,
  unavailable: 3,
};

/**
 * Aggregates a `CommandFreshnessInput` into a single worst-status-wins
 * `ProjectionFreshness`, or `null` if every input is `null` (e.g. every
 * section failed to load). `null` inputs (a section that threw, per
 * FR-CMD-1) are skipped rather than treated as `unavailable` — a section
 * that never returned an answer isn't proof it's behind, it's an
 * independent failure already surfaced by that section's own ErrorBanner.
 */
export function rollupFreshness(
  input: CommandFreshnessInput,
): ProjectionFreshness | null {
  const candidates = [
    input.opportunities,
    input.applications,
    input.relationships,
    input.outreach,
  ].filter((value): value is ProjectionFreshness => value !== null);
  if (candidates.length === 0) {
    return null;
  }
  return candidates.reduce((worst, candidate) =>
    FRESHNESS_SEVERITY[candidate.status] > FRESHNESS_SEVERITY[worst.status]
      ? candidate
      : worst,
  );
}

// ---------------------------------------------------------------------------
// FR-CMD-3 — Needs Attention rail
// ---------------------------------------------------------------------------

export type NeedsAttentionKind =
  | "outreach-pending-approval"
  | "outreach-approval-expiring"
  | "opportunity-discovered"
  | "operation-active";

export interface NeedsAttentionItem {
  readonly id: string;
  readonly kind: NeedsAttentionKind;
  readonly title: string;
  readonly reason: string;
  readonly href: string;
}

/**
 * `Outreach` (the SDK projection type) carries `approvalContractId`, not an
 * expiry — the expiry lives on the referenced `ApprovalEvidence`
 * (`getApproval`). `+page.svelte` resolves `approvalExpiresAt` for
 * `approved` outreach items before calling `buildNeedsAttention`; this
 * keeps the ordering rule here pure and unit-testable with synthetic
 * timestamps, matching FR-CMD-4's same discipline.
 */
export type OutreachWithApprovalExpiry = Outreach & {
  readonly approvalExpiresAt: string | null;
};

const APPROVAL_EXPIRY_WINDOW_MS = 4 * 60 * 60 * 1000;

/**
 * FR-CMD-3 / risk G1 — expiry is always computed from the timestamp, never
 * trusted from `status` (an `approved` record's `status` never flips to
 * `expired` server-side; PRD §4 governance principle 2). An
 * already-expired approval (`remaining <= 0`) is the stranded state PRD §1
 * calls "the outreach dead end" — it is not "expiring soon," it is already
 * gone, and does not belong in this rail.
 */
export function isApprovalExpiringSoon(
  expiresAt: string | null,
  now: Date,
): boolean {
  if (expiresAt === null) {
    return false;
  }
  const expiryMs = Date.parse(expiresAt);
  if (Number.isNaN(expiryMs)) {
    return false;
  }
  const remainingMs = expiryMs - now.getTime();
  return remainingMs > 0 && remainingMs <= APPROVAL_EXPIRY_WINDOW_MS;
}

/**
 * FR-CMD-3 — builds the Needs Attention rail in the exact required order:
 * outreach `pending_approval`; then outreach `approved` expiring within 4h;
 * then opportunities `discovered`; then operations `pending`/`running`. The
 * two outreach categories and the operations category keep the order they
 * arrived in. The `opportunity-discovered` category is the one exception
 * (CCC Wave 2, Lane G): within that category only, items are ranked score
 * descending with unscored (`fitScore === null`) opportunities last, and
 * excluded-employer matches are dropped entirely — see
 * `opportunity-ranking.ts`. This is intra-category ordering only; it never
 * moves the `opportunity-discovered` category itself relative to the other
 * three.
 */
export function buildNeedsAttention(
  bundle: {
    readonly outreach: readonly OutreachWithApprovalExpiry[];
    readonly opportunities: readonly Opportunity[];
    readonly operations: readonly Operation[];
  },
  now: Date = new Date(),
): NeedsAttentionItem[] {
  const items: NeedsAttentionItem[] = [];

  for (const item of bundle.outreach) {
    if (item.status === "pending_approval") {
      items.push({
        id: item.outreachId,
        kind: "outreach-pending-approval",
        title: `Outreach to ${item.channel} contact awaiting approval`,
        reason: "pending_approval",
        href: `/outreach/${item.outreachId}`,
      });
    }
  }

  for (const item of bundle.outreach) {
    if (item.status === "approved" && isApprovalExpiringSoon(item.approvalExpiresAt, now)) {
      items.push({
        id: item.outreachId,
        kind: "outreach-approval-expiring",
        title: `Outreach approval expires within 4h`,
        reason: "approved, expiresAt inside 4h window",
        href: `/outreach/${item.outreachId}`,
      });
    }
  }

  // CCC Wave 2, Lane G — intra-category ordering only (FR-CMD-3's
  // cross-category order above is unchanged: this still runs after the two
  // outreach passes and before the operations pass). Within
  // `opportunity-discovered`, rank by score descending with unscored
  // (`fitScore === null`) opportunities last, and drop excluded-employer
  // matches entirely — an excluded employer must never surface as "needs
  // attention," score notwithstanding (Lane F1's scorer always gives an
  // excluded match `fitScore === 0`, which is exactly the value a rail
  // ordered "best first" would otherwise bury at the bottom instead of
  // omitting, so this filters by `isExcludedOpportunity` on the
  // explanation, never by score).
  const discovered = bundle.opportunities.filter(
    (item) => item.status === "discovered" && !isExcludedOpportunity(item),
  );
  for (const item of rankOpportunitiesByScore(discovered)) {
    items.push({
      id: item.opportunityId,
      kind: "opportunity-discovered",
      title: `${item.employer} — ${item.title}`,
      reason: "discovered",
      href: `/opportunities/${item.opportunityId}`,
    });
  }

  for (const item of bundle.operations) {
    if (item.status === "pending" || item.status === "running") {
      items.push({
        id: item.id,
        kind: "operation-active",
        title: `${item.command} — ${item.status}`,
        reason: item.status,
        href: `/operations/${item.id}`,
      });
    }
  }

  return items;
}

// ---------------------------------------------------------------------------
// FR-CMD-4 — past-nextActionAt rule (unfireable today, unit-tested)
// ---------------------------------------------------------------------------

/**
 * FR-CMD-4 — `Application.nextActionAt` is permanently `null` in live data
 * today (PRD §11.3, BE-6: no command originates an Application row at
 * all). This rule must still exist and be correct, proven only by synthetic
 * data in `command-home.test.ts` — it must not silently vanish for lack of
 * live rows to exercise it against.
 */
export function isNextActionOverdue(application: Application, now: Date): boolean {
  if (application.nextActionAt === null) {
    return false;
  }
  const dueMs = Date.parse(application.nextActionAt);
  if (Number.isNaN(dueMs)) {
    return false;
  }
  return dueMs < now.getTime();
}

export function overdueApplications(
  applications: readonly Application[],
  now: Date = new Date(),
): readonly Application[] {
  return applications.filter((application) => isNextActionOverdue(application, now));
}

// ---------------------------------------------------------------------------
// FR-CMD-5 — single centered empty state on a fresh install
// ---------------------------------------------------------------------------

/**
 * FR-CMD-5 — a fresh install is signalled by Opportunities and Operations
 * both being ever-empty (true-zero, not filtered or errored). Applications
 * and Outreach are excluded from this gate deliberately: both are
 * permanently empty today regardless of install age (BE-6 / adapter
 * binding, PRD §2.2), so including them would make every session today
 * read as "fresh install." Relationships is excluded for the same reason,
 * just the opposite direction: it's the ~2242-row projection the ambient
 * Dex sweep feeds (see the FR-CMD-2 supervisor decision above), so it would
 * plausibly have rows on any install with a Dex sync configured, install
 * age notwithstanding — including it would make this gate fire *less*
 * reliably, not more. It is also not loaded as `readonly Relationship[]`
 * anywhere on this page (only its page-level freshness is fetched), so
 * there is nothing here to gate on even mechanically.
 */
export function isCommandHomeFreshInstall(
  opportunities: readonly Opportunity[],
  operations: readonly Operation[],
): boolean {
  return opportunities.length === 0 && operations.length === 0;
}
