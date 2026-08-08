<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  let {
    title,
    meta = undefined,
    children,
    class: className = "",
    ...rest
  }: HTMLAttributes<HTMLElement> & {
    title: string;
    meta?: string;
    children?: Snippet;
    class?: string;
  } = $props();
</script>

<section class={`rh-panel ${className}`.trim()} {...rest}>
  <header class="rh-panel__header">
    <h2 class="rh-panel__title">{title}</h2>
    {#if meta}
      <span class="rh-panel__meta">{meta}</span>
    {/if}
  </header>
  <div class="rh-panel__body">
    {@render children?.()}
  </div>
</section>
