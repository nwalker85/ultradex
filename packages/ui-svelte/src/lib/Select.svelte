<script lang="ts">
  import type { HTMLSelectAttributes } from "svelte/elements";

  export type SelectOption = {
    value: string;
    label: string;
  };

  let {
    label,
    options = [],
    value = $bindable(""),
    id = undefined,
    class: className = "",
    ...rest
  }: HTMLSelectAttributes & {
    label: string;
    options?: readonly SelectOption[];
    value?: string;
    class?: string;
  } = $props();

  const selectId = id ?? `rh-select-${label.replace(/\s+/g, "-").toLowerCase()}`;
</script>

<label class={`rh-field ${className}`.trim()} for={selectId}>
  <span class="rh-field__label">{label}</span>
  <select class="rh-select" id={selectId} bind:value {...rest}>
    {#each options as option}
      <option value={option.value}>{option.label}</option>
    {/each}
  </select>
</label>
