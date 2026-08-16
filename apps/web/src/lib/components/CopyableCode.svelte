<script lang="ts">
  import { Button } from "@ravenhelm/ui-svelte";

  /**
   * FR-EVID-1 — any id/hash/opaque ref must render through this component
   * (truncated, monospace, copy affordance), never as a raw untruncated
   * string in prose.
   */
  let {
    value,
    edgeChars = 10,
    copyLabel = "Copy",
  }: {
    value: string;
    /** Characters kept on each side of the ellipsis when truncating. */
    edgeChars?: number;
    copyLabel?: string;
  } = $props();

  let copied = $state(false);
  let resetTimer: ReturnType<typeof setTimeout> | undefined;

  const display = $derived(
    value.length > edgeChars * 2 + 1
      ? `${value.slice(0, edgeChars)}…${value.slice(-edgeChars)}`
      : value,
  );

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard?.writeText(value);
      copied = true;
    } catch {
      copied = false;
      return;
    }
    if (resetTimer !== undefined) {
      clearTimeout(resetTimer);
    }
    resetTimer = setTimeout(() => {
      copied = false;
    }, 1500);
  }
</script>

<span class="ccc-copyable-code">
  <code class="ccc-copyable-code__value" title={value}>{display}</code>
  <Button
    variant="ghost"
    onclick={() => void copy()}
    aria-label={`${copyLabel} ${value}`}
  >
    {copied ? "Copied" : copyLabel}
  </Button>
</span>

<style>
  .ccc-copyable-code {
    align-items: center;
    display: inline-flex;
    gap: var(--rh-space-4);
    max-width: 100%;
  }

  .ccc-copyable-code__value {
    font-family: var(--rh-mono);
    font-size: 0.8rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
