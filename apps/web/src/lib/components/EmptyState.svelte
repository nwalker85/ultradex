<script lang="ts">
  import type { Snippet } from "svelte";

  /**
   * Generic centered empty state. Used for true-stub routes in this slice
   * (Phase 1 foundation) and reused later for the honest empty states named
   * throughout the PRD (e.g. FR-CMD-5, FR-OPP-2, FR-APP-2, FR-SRC-1).
   */
  let {
    title,
    description = undefined,
    children,
  }: {
    title: string;
    description?: string;
    children?: Snippet;
  } = $props();
</script>

<div class="ccc-empty-state" role="status">
  <p class="ccc-empty-state__title">{title}</p>
  {#if description}
    <p class="ccc-empty-state__description">{description}</p>
  {/if}
  {#if children}
    <div class="ccc-empty-state__actions">{@render children()}</div>
  {/if}
</div>

<style>
  .ccc-empty-state {
    align-items: center;
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-8);
    justify-content: center;
    padding: var(--rh-space-24);
    text-align: center;
  }

  .ccc-empty-state__title {
    color: var(--rh-ink);
    font-weight: var(--rh-typography-weight-semibold);
    margin: 0;
  }

  .ccc-empty-state__description {
    color: var(--rh-muted);
    margin: 0 auto;
    max-width: 34rem;
  }

  .ccc-empty-state__actions {
    display: flex;
    gap: var(--rh-space-8);
    margin-top: var(--rh-space-8);
  }
</style>
