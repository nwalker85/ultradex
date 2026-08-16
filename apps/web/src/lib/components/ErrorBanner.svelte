<script lang="ts">
  import { Banner } from "@ravenhelm/ui-svelte";

  import { normalizeError } from "$lib/errors";

  /**
   * FR-GW-6 — renders any thrown value (from the Ultradex SDK or elsewhere)
   * as a plain headline plus every structured detail line, collapsed behind
   * a disclosure. Replaces every ad hoc `{error}` / `err.message` render in
   * the app. Never pass a pre-stringified message here — pass the raw
   * caught value so no structured detail is thrown away before it gets
   * here.
   */
  let { error }: { error: unknown } = $props();

  const normalized = $derived(normalizeError(error));
</script>

<Banner tone="danger">
  <p class="ccc-error-banner__headline">{normalized.headline}</p>
  {#if normalized.details.length > 0}
    <details class="ccc-error-banner__details">
      <summary>Structured detail ({normalized.kind})</summary>
      <dl class="ccc-error-banner__list">
        {#each normalized.details as detail (detail.label)}
          <dt>{detail.label}</dt>
          <dd><pre>{detail.value}</pre></dd>
        {/each}
      </dl>
    </details>
  {/if}
</Banner>

<style>
  .ccc-error-banner__headline {
    margin: 0;
  }

  .ccc-error-banner__details {
    margin-top: var(--rh-space-8);
  }

  .ccc-error-banner__details summary {
    color: var(--rh-muted);
    cursor: pointer;
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
  }

  .ccc-error-banner__list {
    display: grid;
    gap: var(--rh-space-4);
    margin: var(--rh-space-8) 0 0;
  }

  .ccc-error-banner__list dt {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .ccc-error-banner__list dd {
    margin: 0 0 var(--rh-space-8);
  }

  .ccc-error-banner__list pre {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius-6);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    margin: 0;
    overflow-x: auto;
    padding: var(--rh-space-8);
    white-space: pre-wrap;
    word-break: break-word;
  }
</style>
