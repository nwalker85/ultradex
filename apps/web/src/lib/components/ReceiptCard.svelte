<script lang="ts">
  import type { ExecutionReceiptEvidence } from "@ultradex/sdk";

  import CopyableCode from "./CopyableCode.svelte";
  import ErrorBanner from "./ErrorBanner.svelte";

  /**
   * NFR-8 — the one component that owns receipt rendering; no screen
   * re-implements this inline. `getExecutionReceipt` is fetched for all
   * three terminal outcomes (FR-GW-8), including `refused`.
   */
  let {
    receipt,
    error = null,
  }: {
    receipt: ExecutionReceiptEvidence | null;
    error?: unknown;
  } = $props();
</script>

<div class="ccc-receipt-card">
  {#if error}
    <ErrorBanner {error} />
  {:else if receipt === null}
    <p class="ccc-empty">No receipt recorded yet for this operation.</p>
  {:else}
    <dl class="ccc-receipt-card__grid">
      <dt>Receipt</dt>
      <dd><CopyableCode value={receipt.receiptId} /></dd>
      <dt>Receipt status</dt>
      <dd>{receipt.status}</dd>
      <dt>Completed</dt>
      <dd>{receipt.completedAt}</dd>
    </dl>

    <!--
      FR-OPS-6 / governance principle 5 / risk G4 — proofStatus renders as
      the literal string, plain text, no lock/shield/seal/checkmark icon
      anywhere near it. It means Ultradex recorded that this happened; it is
      explicitly not a claim of cryptographic verification.
    -->
    <p class="ccc-receipt-card__proof-status">
      proofStatus: <strong>{receipt.proofStatus}</strong> — Ultradex recorded that this
      happened. This is not a claim of cryptographic verification.
    </p>

    <!-- FR-OPS-7 — cryptographic detail collapsed by default. -->
    <details class="ccc-receipt-card__crypto">
      <summary>Cryptographic detail</summary>
      <dl class="ccc-receipt-card__grid">
        <dt>Event ID</dt>
        <dd><CopyableCode value={receipt.eventId} /></dd>
        <dt>Signature algorithm</dt>
        <dd class="ccc-mono">{receipt.payload.signature.algorithm}</dd>
        <dt>Signature</dt>
        <dd><CopyableCode value={receipt.payload.signature.signature} edgeChars={12} /></dd>
        <dt>Action commitment digest</dt>
        <dd><CopyableCode value={receipt.payload.action_commitment.digest} /></dd>
        <dt>DAML transaction</dt>
        <dd>
          {#if receipt.payload.daml_transaction}
            {receipt.payload.daml_transaction.status}
            {#if receipt.payload.daml_transaction.transaction_id}
              — <CopyableCode value={receipt.payload.daml_transaction.transaction_id} />
            {/if}
          {:else}
            None recorded.
          {/if}
        </dd>
      </dl>
    </details>
  {/if}
</div>

<style>
  .ccc-receipt-card {
    display: grid;
    gap: var(--rh-space-8);
  }

  .ccc-receipt-card__grid {
    display: grid;
    gap: var(--rh-space-4) var(--rh-space-12);
    grid-template-columns: max-content 1fr;
    margin: 0;
  }

  .ccc-receipt-card__grid dt {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .ccc-receipt-card__grid dd {
    margin: 0;
  }

  .ccc-receipt-card__proof-status {
    color: var(--rh-muted);
    margin: 0;
  }

  .ccc-receipt-card__crypto summary {
    color: var(--rh-muted);
    cursor: pointer;
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
  }

  .ccc-receipt-card__crypto[open] summary {
    margin-bottom: var(--rh-space-8);
  }
</style>
