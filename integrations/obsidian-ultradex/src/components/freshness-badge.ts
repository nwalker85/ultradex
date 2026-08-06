import type {
  ProjectionFreshness,
  ProjectionStatus,
} from "@ultradex/sdk";

const FRESHNESS_LABELS: Readonly<Record<ProjectionStatus, string>> = {
  fresh: "Fresh",
  stale: "Stale",
  replaying: "Replaying",
  unavailable: "Unavailable",
};

export function renderFreshnessBadge(
  container: HTMLElement,
  freshness: ProjectionFreshness | null,
): HTMLSpanElement {
  const state = freshness?.status ?? "unavailable";
  return container.createSpan({
    cls: "ultradex-freshness-badge",
    text: FRESHNESS_LABELS[state],
    attr: {
      "data-state": state,
      title:
        freshness === null
          ? "Projection checkpoint is unavailable"
          : `Projection lag ${Math.round(freshness.lagMs)} ms`,
    },
  });
}
