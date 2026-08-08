<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  let {
    columns,
    caption = undefined,
    children,
    class: className = "",
    ...rest
  }: HTMLAttributes<HTMLTableElement> & {
    columns: readonly string[];
    caption?: string;
    children?: Snippet;
    class?: string;
  } = $props();
</script>

<table class={`rh-table ${className}`.trim()} {...rest}>
  {#if caption}
    <caption class="rh-visually-hidden">{caption}</caption>
  {/if}
  <thead>
    <tr>
      {#each columns as column}
        <th scope="col">{column}</th>
      {/each}
    </tr>
  </thead>
  <tbody>
    {@render children?.()}
  </tbody>
</table>

<style>
  :global(.rh-visually-hidden) {
    border: 0;
    clip: rect(0 0 0 0);
    height: 1px;
    margin: -1px;
    overflow: hidden;
    padding: 0;
    position: absolute;
    width: 1px;
  }
</style>
