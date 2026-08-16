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
   * `opportunities.create` (FR-OPP-5..6, section 5 workflow 2) — the one
   * command proven to succeed end to end in this system's history. Wired
   * fully through the governed-write pattern: Tier 1 submission below,
   * Tier 2 resolution via <OperationTracker>.
   */
  let {
    client,
    onCreated = undefined,
  }: {
    client: UltradexClient;
    onCreated?: () => void;
  } = $props();

  let employer = $state("");
  let title = $state("");
  let sourceEvidenceId = $state("");
  let submitting = $state(false);
  let lastOutcome = $state<Tier1Outcome | null>(null);
  let lastError = $state<unknown>(null);
  let activeOperationId = $state<string | null>(null);
  let activeInitialHandle = $state<ContractHandle | undefined>(undefined);

  const canSubmit = $derived(
    !submitting && employer.trim() !== "" && title.trim() !== "" && sourceEvidenceId.trim() !== "",
  );

  const showBanner = $derived(
    lastOutcome !== null && lastOutcome.kind !== "accepted" && lastOutcome.kind !== "already-terminal",
  );

  async function submit(): Promise<void> {
    submitting = true;
    const { outcome, error } = await submitGoverned((idempotencyKey) =>
      client.submitOpportunityCreate({ employer, title, sourceEvidenceId }, { idempotencyKey }),
    );
    submitting = false;
    lastOutcome = outcome;
    lastError = error;

    if (outcome.kind === "accepted" || outcome.kind === "already-terminal") {
      activeOperationId = outcome.handle.operationId;
      activeInitialHandle = outcome.kind === "already-terminal" ? outcome.handle : undefined;
      // FR-GW-3 is about 409 leaving the composer open with values intact —
      // on a real submission we leave the fields as-is too (no reset here);
      // OperationTracker's onCompleted below is what re-fetches the list.
    }
  }
</script>

<div class="ccc-create-opportunity">
  <div class="ccc-grid ccc-grid--two">
    <Field label="Employer" bind:value={employer} disabled={submitting} />
    <Field label="Title" bind:value={title} disabled={submitting} />
  </div>
  <Field
    label="Source evidence ID"
    bind:value={sourceEvidenceId}
    disabled={submitting}
    placeholder="evidence:…"
  />
  <!--
    FR-OPP-5/6 — plain Field, not a picker (no listEvidence query exists).
    Help text points only at copying an id from an existing opportunity's
    Evidence tab. It must NOT suggest evidence.export: that ref passes
    client-side format validation and then refuses server-side with
    source_evidence_not_found.
  -->
  <p class="ccc-empty">
    Copy an evidence id from an existing opportunity's Evidence section. There is no
    picker for this field yet.
  </p>

  <div class="ccc-actions">
    <Button variant="primary" onclick={() => void submit()} disabled={!canSubmit}>
      {submitting ? "Submitting…" : "Create opportunity"}
    </Button>
  </div>

  {#if showBanner && lastOutcome}
    {#if tier1OutcomeCopy(lastOutcome)}
      <Banner tone={toBannerTone(tier1OutcomeTone(lastOutcome))}>{tier1OutcomeCopy(lastOutcome)}</Banner>
    {/if}
    <ErrorBanner error={lastError} />
  {/if}

  {#if activeOperationId}
    <OperationTracker
      {client}
      operationId={activeOperationId}
      initialHandle={activeInitialHandle}
      onCompleted={onCreated}
    />
  {/if}
</div>

<style>
  .ccc-create-opportunity {
    display: grid;
    gap: var(--rh-space-12);
  }
</style>
