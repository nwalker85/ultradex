<script lang="ts">
  import { Badge, Banner } from "@ravenhelm/ui-svelte";
  import type { ContractHandle, UltradexReadClient } from "@ultradex/sdk";

  import { cannedReasonCopy } from "$lib/governed-write.js";
  import { getOperationTracker } from "$lib/operation-tracker.svelte.js";
  import CopyableCode from "./CopyableCode.svelte";
  import ErrorBanner from "./ErrorBanner.svelte";
  import ReceiptCard from "./ReceiptCard.svelte";

  /**
   * Tier 2 of the governed-write pattern (PRD section 8.2), reusable by any
   * write screen. Backed by the page-scoped, deduped `OperationTrackerState`
   * (operation-tracker.svelte.ts) — polls `getOperation` at 1.5s with capped
   * backoff until terminal (FR-GW-7), unless `initialHandle` is already
   * terminal (the 503 dispatch-failure path), in which case it fetches once
   * and never starts a polling loop (FR-GW-2).
   */
  let {
    client,
    operationId,
    initialHandle = undefined,
    onCompleted = undefined,
  }: {
    client: Pick<UltradexReadClient, "getOperation" | "getExecutionReceipt">;
    operationId: string;
    initialHandle?: ContractHandle;
    onCompleted?: () => void;
  } = $props();

  const tracker = $derived(getOperationTracker(client, operationId));

  $effect(() => {
    if (initialHandle !== undefined) {
      tracker.markKnownTerminal(initialHandle);
    } else {
      tracker.start();
    }
  });

  let notified = false;
  $effect(() => {
    if (!notified && tracker.phase === "terminal" && tracker.operation?.status === "completed") {
      notified = true;
      onCompleted?.();
    }
  });

  const statusLabel = $derived(tracker.operation?.status ?? initialHandle?.status ?? "pending");
  const reasonCode = $derived(tracker.operation?.error ?? null);
  const receiptCategory = $derived(tracker.receipt?.reasonCode ?? null);
  const cannedCopy = $derived(cannedReasonCopy(reasonCode));
</script>

<div class="ccc-operation-tracker">
  <div class="ccc-operation-tracker__header">
    <Badge tone={tracker.tone}>{statusLabel}</Badge>
    <span class="ccc-mono">
      Operation <CopyableCode value={operationId} />
    </span>
  </div>

  {#if tracker.phase === "polling"}
    <p class="ccc-empty">Waiting for the operation to resolve — checking every ~1.5s.</p>
  {/if}

  {#if tracker.pollError}
    <ErrorBanner error={tracker.pollError} />
  {/if}

  {#if tracker.phase === "terminal"}
    {#if cannedCopy}
      <!-- FR-OPS-5 — canned, plain-language copy for the four *_unbound codes. -->
      <Banner tone="warning">{cannedCopy}</Banner>
    {/if}

    {#if reasonCode !== null || receiptCategory !== null}
      <!--
        FR-OPS-4 — both reason-code vocabularies visible at the same glance
        level: the granular operation.error and the coarse receipt.reasonCode
        enum, neither hidden behind a disclosure the other isn't.
      -->
      <dl class="ccc-operation-tracker__reasons">
        <dt>Reason code</dt>
        <dd>{reasonCode ?? "—"}</dd>
        <dt>Reason category</dt>
        <dd>{receiptCategory ?? "—"}</dd>
      </dl>
    {/if}

    <ReceiptCard receipt={tracker.receipt} error={tracker.receiptError} />
  {/if}
</div>

<style>
  .ccc-operation-tracker {
    display: grid;
    gap: var(--rh-space-8);
  }

  .ccc-operation-tracker__header {
    align-items: center;
    display: flex;
    gap: var(--rh-space-8);
  }

  .ccc-operation-tracker__reasons {
    display: grid;
    gap: var(--rh-space-4) var(--rh-space-12);
    grid-template-columns: max-content 1fr;
    margin: 0;
  }

  .ccc-operation-tracker__reasons dt {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .ccc-operation-tracker__reasons dd {
    margin: 0;
  }
</style>
