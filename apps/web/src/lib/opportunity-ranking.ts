import type { Opportunity } from "@ultradex/sdk";

/**
 * CCC Wave 2, Lane G — pure score/ranking/partitioning logic for Opportunity
 * rows, kept client-free and unit-testable (same discipline as
 * `command-home.ts`). Two call sites share this module:
 *
 * - `routes/opportunities/+page.svelte` (list view, `partitionOpportunitiesForList`)
 * - `command-home.ts`'s `buildNeedsAttention` (Needs Attention rail,
 *   `rankOpportunitiesByScore` composed with a local `status === "discovered"`
 *   filter — status filtering is a command-home concern and stays there, only
 *   the score/null/excluded primitives live here).
 *
 * Field-naming note (verified against `sdk/typescript/src/contracts.ts` on
 * `origin/main`, 2026-08-16): the wire/SDK `Opportunity` type does **not**
 * carry fields literally named `score` / `score_explanation`. The backend
 * ORM row (`core/jobsearch_models.py::OpportunityProjectionDB`) has had
 * `score` (Float, nullable) / `score_explanation` (String, nullable) columns
 * since the projection was built, but the GraphQL/SDK boundary
 * (`core/jobsearch_projections.py`) maps them to `fitScore` / `fitExplanation`
 * on the way out (`"fit_score": row.score, "fit_explanation":
 * row.score_explanation`). This module operates on the real SDK field names,
 * `Opportunity.fitScore` / `Opportunity.fitExplanation` — there is no
 * `score` / `score_explanation` field to read on the client. See the Wave 2
 * PR description for the loud flag on this naming mismatch.
 */

/**
 * Lane F1's deterministic scorer (`core/jobsearch_scoring.py::compute_score`)
 * marks an excluded-employer match with `score=0` and an explanation that
 * always begins with the literal prefix `"excluded"` (e.g. `"excluded:
 * employer in exclusions (...) — '<employer>' matches exclusion entry
 * '<entry>'"`). Detecting "excluded" from score alone is unsafe — a
 * legitimately scored opportunity can also land on 0 (e.g. every rule
 * unmatched) — so this checks the explanation text, never `fitScore === 0`.
 */
export function isExcludedOpportunity(
  opportunity: Pick<Opportunity, "fitExplanation">,
): boolean {
  return (opportunity.fitExplanation ?? "").toLowerCase().startsWith("excluded");
}

/**
 * Score-descending comparator with nulls (unscored) sorted last. Never
 * treats `null` as `0` — a `null` `fitScore` means "Intent not yet set / the
 * scorer never ran," not "scored zero." Ties (including two `null`s) keep
 * their relative input order — `Array.prototype.sort` is a stable sort per
 * the ECMAScript spec (guaranteed since ES2019, which is well within this
 * project's target runtimes), so no secondary tiebreak key is needed here.
 */
export function compareOpportunitiesByScoreDescNullsLast(
  a: Pick<Opportunity, "fitScore">,
  b: Pick<Opportunity, "fitScore">,
): number {
  if (a.fitScore === b.fitScore) {
    return 0;
  }
  if (a.fitScore === null) {
    return 1;
  }
  if (b.fitScore === null) {
    return -1;
  }
  return b.fitScore - a.fitScore;
}

/**
 * Returns a new array (input is never mutated) sorted score-descending,
 * nulls last, stable on ties.
 */
export function rankOpportunitiesByScore(
  opportunities: readonly Opportunity[],
): Opportunity[] {
  return [...opportunities].sort(compareOpportunitiesByScoreDescNullsLast);
}

export interface PartitionedOpportunities {
  /** Non-excluded, `fitScore !== null`, sorted score-descending. */
  readonly scored: readonly Opportunity[];
  /** Non-excluded, `fitScore === null` (Intent not yet set / never scored). Input order preserved. */
  readonly unscored: readonly Opportunity[];
  /** Excluded-employer matches (`fitExplanation` starts with "excluded"). Input order preserved. */
  readonly excluded: readonly Opportunity[];
}

/**
 * Opportunities-list ordering (Lane G item 1): scored opportunities first,
 * ranked score-descending; unscored (`fitScore === null`) grouped below
 * under a visible divider; excluded employers grouped last under their own
 * divider, muted, with the exclusion explanation shown. Excluded items are
 * partitioned out *before* the scored/unscored split so an excluded match
 * (always `fitScore === 0` from the scorer) never gets mistaken for a
 * genuine 0-scored, non-excluded opportunity.
 */
export function partitionOpportunitiesForList(
  opportunities: readonly Opportunity[],
): PartitionedOpportunities {
  const excluded: Opportunity[] = [];
  const eligible: Opportunity[] = [];
  for (const opportunity of opportunities) {
    (isExcludedOpportunity(opportunity) ? excluded : eligible).push(opportunity);
  }

  const scored: Opportunity[] = [];
  const unscored: Opportunity[] = [];
  for (const opportunity of eligible) {
    (opportunity.fitScore === null ? unscored : scored).push(opportunity);
  }

  return {
    scored: rankOpportunitiesByScore(scored),
    unscored,
    excluded,
  };
}
