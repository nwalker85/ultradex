import type {
  Opportunity,
  OpportunityPage,
  ProjectionFreshness,
  Relationship,
  RelationshipPage,
} from "@ultradex/sdk";

export type WhatsNextItem = {
  readonly id: string;
  readonly title: string;
  readonly reason: string;
  readonly kind: "opportunity" | "relationship" | "empty";
};

export function pickWhatsNext(
  opportunities: readonly Opportunity[],
  relationships: readonly Relationship[],
): WhatsNextItem {
  const active = opportunities.filter((item) => item.status !== "archived");
  const qualified = active.find((item) => item.status === "qualified");
  if (qualified) {
    return {
      id: qualified.opportunityId,
      title: `${qualified.employer} — ${qualified.title}`,
      reason: "Qualified opportunity waiting on next Consent action",
      kind: "opportunity",
    };
  }
  const watching = active.find((item) => item.status === "watching");
  if (watching) {
    return {
      id: watching.opportunityId,
      title: `${watching.employer} — ${watching.title}`,
      reason: "Watching — warm network available; score or outreach next",
      kind: "opportunity",
    };
  }
  if (active[0]) {
    return {
      id: active[0].opportunityId,
      title: `${active[0].employer} — ${active[0].title}`,
      reason: `State: ${active[0].status}`,
      kind: "opportunity",
    };
  }
  if (relationships[0]) {
    return {
      id: relationships[0].relationshipId,
      title: relationships[0].relevanceSummary ?? relationships[0].dexContactRef,
      reason: "Relationship projection present without opportunities",
      kind: "relationship",
    };
  }
  return {
    id: "none",
    title: "Nothing queued",
    reason: "No career projections yet — Sense / create still empty",
    kind: "empty",
  };
}

export function freshnessLabel(
  freshness: ProjectionFreshness | null | undefined,
): string {
  if (!freshness) {
    return "unavailable";
  }
  return `${freshness.status} · lag ${Math.round(freshness.lagMs)}ms`;
}

export type ProjectionBundle = {
  opportunities: OpportunityPage;
  relationships: RelationshipPage;
};
