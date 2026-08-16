<script lang="ts">
  import { Banner, Button, Field } from "@ravenhelm/ui-svelte";
  import type { ContractHandle, UltradexClient } from "@ultradex/sdk";

  import {
    submitGoverned,
    tier1OutcomeCopy,
    tier1OutcomeTone,
    toBannerTone,
    type Tier1Outcome,
  } from "$lib/governed-write.js";
  import ErrorBanner from "./ErrorBanner.svelte";
  import OperationTracker from "./OperationTracker.svelte";

  /**
   * `opportunities.score` (FR-OPP-7). Refuses today with `scorer_unbound` —
   * <OperationTracker> renders that as a legible, warning-toned refusal
   * with canned copy (FR-OPS-5), not a generic error. `lens` stays free
   * text per PRD section 11.5 (no enum exists yet).
   */
  let {
    client,
    opportunityId,
  }: {
    client: UltradexClient;
    opportunityId: string;
  } = $props();

  let lens = $state("");
  let submitting = $state(false);
  let lastOutcome = $state<Tier1Outcome | null>(null);
  let lastError = $state<unknown>(null);
  let activeOperationId = $state<string | null>(null);
  let activeInitialHandle = $state<ContractHandle | undefined>(undefined);

  const showBanner = $derived(
    lastOutcome !== null && lastOutcome.kind !== "accepted" && lastOutcome.kind !== "already-terminal",
  );

  async function submit(): Promise<void> {
    submitting = true;
    const { outcome, error } = await submitGoverned((idempotencyKey) =>
      client.submitOpportunityScore({ opportunityId, lens }, { idempotencyKey }),
    );
    submitting = false;
    lastOutcome = outcome;
    lastError = error;
    if (outcome.kind === "accepted" || outcome.kind === "already-terminal") {
      activeOperationId = outcome.handle.operationId;
      activeInitialHandle = outcome.kind === "already-terminal" ? outcome.handle : undefined;
    }
  }
</script>

<div class="ccc-governed-action">
  <Field label="Lens (free text)" bind:value={lens} disabled={submitting} placeholder="e.g. staff-plus-ic" />
  <div class="ccc-actions">
    <Button onclick={() => void submit()} disabled={submitting || lens.trim() === ""}>
      {submitting ? "Submitting…" : "Score"}
    </Button>
  </div>

  {#if showBanner && lastOutcome}
    {#if tier1OutcomeCopy(lastOutcome)}
      <Banner tone={toBannerTone(tier1OutcomeTone(lastOutcome))}>{tier1OutcomeCopy(lastOutcome)}</Banner>
    {/if}
    <ErrorBanner error={lastError} />
  {/if}

  {#if activeOperationId}
    <OperationTracker {client} operationId={activeOperationId} initialHandle={activeInitialHandle} />
  {/if}
</div>

<style>
  .ccc-governed-action {
    display: grid;
    gap: var(--rh-space-12);
  }
</style>
