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
   * `relationships.sync` (FR-OPP-8). Refuses today with
   * `relationship_resolver_unbound` — <OperationTracker> renders that as a
   * legible, warning-toned refusal with canned copy (FR-OPS-5), not a
   * generic error. FR-REL-2 (no bare "New relationship" entry point) is
   * satisfied structurally: this action only exists here, scoped to a
   * specific opportunityId, never as a standalone composer.
   */
  let {
    client,
    opportunityId,
  }: {
    client: UltradexClient;
    opportunityId: string;
  } = $props();

  let dexContactRef = $state("");
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
      client.submitRelationshipSync({ opportunityId, dexContactRef }, { idempotencyKey }),
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
  <Field
    label="Dex contact ref"
    bind:value={dexContactRef}
    disabled={submitting}
    placeholder="dex:contact-id"
  />
  <div class="ccc-actions">
    <Button onclick={() => void submit()} disabled={submitting || dexContactRef.trim() === ""}>
      {submitting ? "Submitting…" : "Sync relationship"}
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
