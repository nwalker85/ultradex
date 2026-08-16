<script lang="ts">
  import { Badge } from "@ravenhelm/ui-svelte";
  import type { ProjectionFreshness } from "@ultradex/sdk";

  import { freshnessLabel } from "$lib/whats-next.js";

  /**
   * NFR-8 — the one component that owns freshness rendering; no screen
   * re-implements this inline. Every projection is stamped fresh/lagMs:0
   * today (governance principle 4), so this reads as a quiet success badge
   * now — but the mapping is written to degrade honestly the day a
   * projection actually falls behind (risk G2: keep it legible while it's
   * boring, not hardcoded to always look fresh).
   */
  let { freshness }: { freshness: ProjectionFreshness | null | undefined } = $props();

  const tone = $derived.by((): "neutral" | "success" | "warning" | "danger" => {
    if (!freshness) {
      return "neutral";
    }
    switch (freshness.status) {
      case "fresh":
        return "success";
      case "stale":
        return "warning";
      case "unavailable":
        return "danger";
      case "replaying":
      default:
        return "neutral";
    }
  });
</script>

<Badge {tone}>{freshnessLabel(freshness)}</Badge>
