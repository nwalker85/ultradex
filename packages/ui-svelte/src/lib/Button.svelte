<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLButtonAttributes } from "svelte/elements";

  type Variant = "primary" | "secondary" | "ghost" | "danger";

  let {
    children,
    variant = "secondary",
    type = "button",
    class: className = "",
    ...rest
  }: HTMLButtonAttributes & {
    children?: Snippet;
    variant?: Variant;
    class?: string;
  } = $props();
</script>

<button
  class={`rh-button rh-button--${variant} ${className}`.trim()}
  {type}
  {...rest}
>
  {@render children?.()}
</button>
