<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  let {
    children,
    tone = "neutral",
    /** @deprecated use tone="accent" — brass stub removed */
    brass = false,
    class: className = "",
    ...rest
  }: HTMLAttributes<HTMLSpanElement> & {
    children?: Snippet;
    tone?: "neutral" | "accent" | "success" | "warning" | "danger";
    brass?: boolean;
    class?: string;
  } = $props();

  const resolvedTone = brass && tone === "neutral" ? "accent" : tone;
</script>

<span class={`rh-badge rh-badge--${resolvedTone} ${className}`.trim()} {...rest}>
  {@render children?.()}
</span>
