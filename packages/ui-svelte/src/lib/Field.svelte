<script lang="ts">
  import type { HTMLInputAttributes } from "svelte/elements";

  let {
    label,
    value = $bindable(""),
    id = undefined,
    class: className = "",
    ...rest
  }: HTMLInputAttributes & {
    label: string;
    value?: string;
    class?: string;
  } = $props();

  const fieldId = id ?? `rh-field-${label.replace(/\s+/g, "-").toLowerCase()}`;
</script>

<label class={`rh-field ${className}`.trim()} for={fieldId}>
  <span class="rh-field__label">{label}</span>
  <input class="rh-input" id={fieldId} bind:value {...rest} />
</label>
