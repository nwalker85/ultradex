<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  type Tone = "info" | "success" | "warning" | "danger";

  let {
    children,
    tone = "info",
    class: className = "",
    ...rest
  }: HTMLAttributes<HTMLDivElement> & {
    children?: Snippet;
    tone?: Tone;
    class?: string;
  } = $props();
</script>

<div class={`rh-banner rh-banner--${tone} ${className}`.trim()} role="status" {...rest}>
  {@render children?.()}
</div>
