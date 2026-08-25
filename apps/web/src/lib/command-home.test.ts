import { describe, expect, it } from "vitest";
import type {
  Application,
  ApplicationPage,
  Operation,
  Opportunity,
  OpportunityPage,
  OutreachPage,
  ProjectionFreshness,
  RelationshipPage,
} from "@ultradex/sdk";

import {
  buildFreshnessRollupInput,
  buildNeedsAttention,
  isApprovalExpiringSoon,
  isCommandHomeFreshInstall,
  isNextActionOverdue,
  overdueApplications,
  rollupFreshness,
  type OutreachWithApprovalExpiry,
} from "./command-home.js";

const NOW = new Date("2026-08-15T12:00:00Z");

function freshness(overrides: Partial<ProjectionFreshness> = {}): ProjectionFreshness {
  return {
    sourceEventId: "e",
    sourceEventPosition: "p",
    projectedAt: "2026-08-15T11:59:00Z",
    lagMs: 0,
    status: "fresh",
    ...overrides,
  };
}

function opportunity(overrides: Partial<Opportunity> & { opportunityId: string }): Opportunity {
  return {
    employer: "Watch Co",
    title: "Role",
    location: null,
    roleFamily: null,
    status: "discovered",
    fitScore: null,
    fitExplanation: null,
    riskFlags: [],
    evidenceRefs: [],
    freshness: freshness(),
    createdAt: "2026-08-15T00:00:00Z",
    updatedAt: "2026-08-15T00:00:00Z",
    ...overrides,
  } as Opportunity;
}

function application(overrides: Partial<Application> & { applicationId: string }): Application {
  return {
    opportunityId: "opportunity-1",
    status: "draft",
    stageHistory: [],
    artifactRefs: [],
    nextAction: null,
    nextActionAt: null,
    freshness: freshness(),
    createdAt: "2026-08-15T00:00:00Z",
    updatedAt: "2026-08-15T00:00:00Z",
    ...overrides,
  } as Application;
}

function outreach(
  overrides: Partial<OutreachWithApprovalExpiry> & { outreachId: string },
): OutreachWithApprovalExpiry {
  return {
    opportunityId: "opportunity-1",
    relationshipId: null,
    status: "draft",
    channel: "gmail",
    messageCommitment: "sha256:" + "0".repeat(64),
    approvalContractId: null,
    sentEvidenceRef: null,
    freshness: freshness(),
    createdAt: "2026-08-15T00:00:00Z",
    updatedAt: "2026-08-15T00:00:00Z",
    approvalExpiresAt: null,
    ...overrides,
  } as OutreachWithApprovalExpiry;
}

function operation(overrides: Partial<Operation> & { id: string }): Operation {
  return {
    correlationId: null,
    command: "opportunities.create",
    status: "completed",
    createdAt: "2026-08-15T00:00:00Z",
    startedAt: "2026-08-15T00:00:00Z",
    completedAt: "2026-08-15T00:00:01Z",
    result: null,
    error: null,
    freshness: null,
    ...overrides,
  } as Operation;
}

function oppPage(overrides: Partial<OpportunityPage> = {}): OpportunityPage {
  return { items: [], freshness: freshness(), nextCursor: null, ...overrides };
}

function appPage(overrides: Partial<ApplicationPage> = {}): ApplicationPage {
  return { items: [], freshness: freshness(), nextCursor: null, ...overrides };
}

function outPage(overrides: Partial<OutreachPage> = {}): OutreachPage {
  return { items: [], freshness: freshness(), nextCursor: null, ...overrides };
}

function relPage(overrides: Partial<RelationshipPage> = {}): RelationshipPage {
  return { items: [], freshness: freshness(), nextCursor: null, ...overrides };
}

describe("buildFreshnessRollupInput / rollupFreshness (FR-CMD-2)", () => {
  it("aggregates worst-status-wins across opportunities, applications, relationships, outreach", () => {
    const input = buildFreshnessRollupInput({
      opportunities: oppPage({ freshness: freshness({ status: "fresh" }) }),
      applications: appPage({ freshness: freshness({ status: "stale" }) }),
      relationships: relPage({ freshness: freshness({ status: "fresh" }) }),
      outreach: outPage({ freshness: freshness({ status: "fresh" }) }),
      operations: [],
    });
    expect(rollupFreshness(input)?.status).toBe("stale");
  });

  it("unavailable outranks stale and replaying", () => {
    const input = buildFreshnessRollupInput({
      opportunities: oppPage({ freshness: freshness({ status: "replaying" }) }),
      applications: appPage({ freshness: freshness({ status: "stale" }) }),
      relationships: relPage({ freshness: freshness({ status: "fresh" }) }),
      outreach: outPage({ freshness: freshness({ status: "unavailable" }) }),
      operations: [],
    });
    expect(rollupFreshness(input)?.status).toBe("unavailable");
  });

  it("relationships' own status can be the worst input — it is a real projection in the rollup, not a bystander", () => {
    const input = buildFreshnessRollupInput({
      opportunities: oppPage({ freshness: freshness({ status: "fresh" }) }),
      applications: appPage({ freshness: freshness({ status: "fresh" }) }),
      relationships: relPage({ freshness: freshness({ status: "unavailable" }) }),
      outreach: outPage({ freshness: freshness({ status: "fresh" }) }),
      operations: [],
    });
    expect(rollupFreshness(input)?.status).toBe("unavailable");
  });

  it("skips sections that failed to load (null freshness) rather than treating them as unavailable", () => {
    const input = buildFreshnessRollupInput({
      opportunities: null,
      applications: appPage({ freshness: freshness({ status: "fresh" }) }),
      relationships: relPage({ freshness: freshness({ status: "fresh" }) }),
      outreach: outPage({ freshness: freshness({ status: "fresh" }) }),
      operations: [],
    });
    expect(rollupFreshness(input)?.status).toBe("fresh");
  });

  it("returns null when every section failed to load", () => {
    const input = buildFreshnessRollupInput({
      opportunities: null,
      applications: null,
      relationships: null,
      outreach: null,
      operations: [],
    });
    expect(rollupFreshness(input)).toBeNull();
  });

  it("REGRESSION (FR-CMD-2): Operation.freshness is never in the rollup input set", () => {
    // Simulate a hypothetical future bug where an Operation somehow carries
    // a non-null, worst-case freshness value. Today this field is
    // hardcoded null server-side (PRD §4 governance principle 4), but the
    // regression test must hold even if that ever changes.
    const poisonedOperationFreshness = freshness({ status: "unavailable", lagMs: 999_999 });
    const poisonedOperations: Operation[] = [
      operation({ id: "op-1", freshness: poisonedOperationFreshness }),
    ];

    const input = buildFreshnessRollupInput({
      opportunities: oppPage({ freshness: freshness({ status: "fresh" }) }),
      applications: appPage({ freshness: freshness({ status: "fresh" }) }),
      relationships: relPage({ freshness: freshness({ status: "fresh" }) }),
      outreach: outPage({ freshness: freshness({ status: "fresh" }) }),
      operations: poisonedOperations,
    });

    // Structural assertion: the rollup input has exactly the four real
    // projection keys, never an "operations" key.
    expect(Object.keys(input).sort()).toEqual([
      "applications",
      "opportunities",
      "outreach",
      "relationships",
    ]);

    // Value assertion: the poisoned operation freshness object never shows
    // up anywhere in the rollup input.
    expect(Object.values(input)).not.toContainEqual(poisonedOperationFreshness);

    // Behavioral assertion: the aggregate stays "fresh" — proving the
    // poisoned "unavailable" value never entered the worst-status-wins
    // computation at all.
    expect(rollupFreshness(input)?.status).toBe("fresh");
  });
});

describe("isApprovalExpiringSoon (FR-CMD-3 / risk G1)", () => {
  it("is true strictly inside the 4h window", () => {
    expect(isApprovalExpiringSoon("2026-08-15T15:59:00Z", NOW)).toBe(true);
  });

  it("is false outside the 4h window", () => {
    expect(isApprovalExpiringSoon("2026-08-15T16:01:00Z", NOW)).toBe(false);
  });

  it("is false once the approval has already expired — never trusted from status", () => {
    expect(isApprovalExpiringSoon("2026-08-15T11:00:00Z", NOW)).toBe(false);
  });

  it("is false when there is no expiry timestamp", () => {
    expect(isApprovalExpiringSoon(null, NOW)).toBe(false);
  });
});

describe("buildNeedsAttention (FR-CMD-3 ordering)", () => {
  it("orders exactly: outreach pending_approval, outreach approved+expiring, opportunities discovered, operations pending/running", () => {
    const items = buildNeedsAttention(
      {
        outreach: [
          outreach({ outreachId: "out-approved-expiring", status: "approved", approvalExpiresAt: "2026-08-15T14:00:00Z" }),
          outreach({ outreachId: "out-pending", status: "pending_approval" }),
          outreach({ outreachId: "out-sent", status: "sent" }),
        ],
        opportunities: [
          opportunity({ opportunityId: "opp-discovered", status: "discovered" }),
          opportunity({ opportunityId: "opp-qualified", status: "qualified" }),
        ],
        operations: [
          operation({ id: "op-running", status: "running" }),
          operation({ id: "op-completed", status: "completed" }),
          operation({ id: "op-pending", status: "pending" }),
        ],
      },
      NOW,
    );

    expect(items.map((item) => item.kind)).toEqual([
      "outreach-pending-approval",
      "outreach-approval-expiring",
      "opportunity-discovered",
      "operation-active",
      "operation-active",
    ]);
    expect(items.map((item) => item.id)).toEqual([
      "out-pending",
      "out-approved-expiring",
      "opp-discovered",
      "op-running",
      "op-pending",
    ]);
  });

  it("excludes approved outreach outside the 4h expiry window", () => {
    const items = buildNeedsAttention(
      {
        outreach: [
          outreach({ outreachId: "out-safe", status: "approved", approvalExpiresAt: "2026-08-16T12:00:00Z" }),
        ],
        opportunities: [],
        operations: [],
      },
      NOW,
    );
    expect(items).toEqual([]);
  });

  it("excludes non-discovered opportunities and non-active operations", () => {
    const items = buildNeedsAttention(
      {
        outreach: [],
        opportunities: [opportunity({ opportunityId: "opp-watching", status: "watching" })],
        operations: [operation({ id: "op-failed", status: "failed" })],
      },
      NOW,
    );
    expect(items).toEqual([]);
  });

  it("returns an empty rail when every bundle is empty", () => {
    expect(buildNeedsAttention({ outreach: [], opportunities: [], operations: [] }, NOW)).toEqual([]);
  });

  describe("opportunity-discovered intra-category ordering (CCC Wave 2, Lane G)", () => {
    it("ranks discovered opportunities by score descending, unscored last", () => {
      const items = buildNeedsAttention(
        {
          outreach: [],
          opportunities: [
            opportunity({ opportunityId: "opp-unscored", status: "discovered", fitScore: null }),
            opportunity({ opportunityId: "opp-high", status: "discovered", fitScore: 90 }),
            opportunity({ opportunityId: "opp-mid", status: "discovered", fitScore: 40 }),
          ],
          operations: [],
        },
        NOW,
      );
      expect(items.map((item) => item.id)).toEqual(["opp-high", "opp-mid", "opp-unscored"]);
    });

    it("never treats a null fitScore as 0 — unscored still ranks below a genuine 0", () => {
      const items = buildNeedsAttention(
        {
          outreach: [],
          opportunities: [
            opportunity({ opportunityId: "opp-unscored", status: "discovered", fitScore: null }),
            opportunity({
              opportunityId: "opp-zero",
              status: "discovered",
              fitScore: 0,
              fitExplanation: "role_family no match (weight=0.4)",
            }),
          ],
          operations: [],
        },
        NOW,
      );
      expect(items.map((item) => item.id)).toEqual(["opp-zero", "opp-unscored"]);
    });

    it("excludes discovered opportunities whose explanation marks them excluded — they never appear, at any score", () => {
      const items = buildNeedsAttention(
        {
          outreach: [],
          opportunities: [
            opportunity({
              opportunityId: "opp-excluded",
              status: "discovered",
              fitScore: 0,
              fitExplanation:
                "excluded: employer in exclusions (current employer) — 'IntelePeer' matches 'IntelePeer'",
            }),
            opportunity({ opportunityId: "opp-kept", status: "discovered", fitScore: 10 }),
          ],
          operations: [],
        },
        NOW,
      );
      expect(items.map((item) => item.id)).toEqual(["opp-kept"]);
    });

    it("does not disturb FR-CMD-3's cross-category order — opportunity-discovered still sits between the two outreach categories and operations", () => {
      const items = buildNeedsAttention(
        {
          outreach: [
            outreach({ outreachId: "out-pending", status: "pending_approval" }),
            outreach({
              outreachId: "out-approved-expiring",
              status: "approved",
              approvalExpiresAt: "2026-08-15T14:00:00Z",
            }),
          ],
          opportunities: [
            opportunity({ opportunityId: "opp-low", status: "discovered", fitScore: 10 }),
            opportunity({ opportunityId: "opp-high", status: "discovered", fitScore: 99 }),
          ],
          operations: [operation({ id: "op-running", status: "running" })],
        },
        NOW,
      );
      expect(items.map((item) => item.kind)).toEqual([
        "outreach-pending-approval",
        "outreach-approval-expiring",
        "opportunity-discovered",
        "opportunity-discovered",
        "operation-active",
      ]);
      expect(items.map((item) => item.id)).toEqual([
        "out-pending",
        "out-approved-expiring",
        "opp-high",
        "opp-low",
        "op-running",
      ]);
    });
  });
});

describe("isNextActionOverdue / overdueApplications (FR-CMD-4)", () => {
  // The live system has 0 application rows and nextActionAt is permanently
  // null today (BE-6 unmerged) — this rule can only be exercised with
  // synthetic data, which is the entire point of this test file existing.

  it("flags an application whose nextActionAt is in the past", () => {
    const overdue = application({ applicationId: "app-overdue", nextActionAt: "2026-08-14T00:00:00Z" });
    expect(isNextActionOverdue(overdue, NOW)).toBe(true);
  });

  it("does not flag an application whose nextActionAt is in the future", () => {
    const upcoming = application({ applicationId: "app-upcoming", nextActionAt: "2026-08-20T00:00:00Z" });
    expect(isNextActionOverdue(upcoming, NOW)).toBe(false);
  });

  it("does not flag an application with a null nextActionAt", () => {
    const noAction = application({ applicationId: "app-none", nextActionAt: null });
    expect(isNextActionOverdue(noAction, NOW)).toBe(false);
  });

  it("filters a mixed list down to only the overdue applications", () => {
    const overdue = application({ applicationId: "app-overdue", nextActionAt: "2026-08-01T00:00:00Z" });
    const upcoming = application({ applicationId: "app-upcoming", nextActionAt: "2026-09-01T00:00:00Z" });
    const noAction = application({ applicationId: "app-none", nextActionAt: null });
    expect(overdueApplications([overdue, upcoming, noAction], NOW)).toEqual([overdue]);
  });

  it("never vanishes for lack of live rows — an empty list yields an empty result, not a throw", () => {
    expect(overdueApplications([], NOW)).toEqual([]);
  });
});

describe("isCommandHomeFreshInstall (FR-CMD-5)", () => {
  it("is true only when both opportunities and operations are ever-empty", () => {
    expect(isCommandHomeFreshInstall([], [])).toBe(true);
  });

  it("is false when opportunities has rows", () => {
    expect(isCommandHomeFreshInstall([opportunity({ opportunityId: "a" })], [])).toBe(false);
  });

  it("is false when operations has rows", () => {
    expect(isCommandHomeFreshInstall([], [operation({ id: "op-1" })])).toBe(false);
  });

  it("is false when both have rows", () => {
    expect(
      isCommandHomeFreshInstall([opportunity({ opportunityId: "a" })], [operation({ id: "op-1" })]),
    ).toBe(false);
  });
});
