<script lang="ts">
  import { page } from "$app/state";

  import { loadConfig, operatorAuthMissing, type GlassConfig } from "$lib/client";
  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import EntityNotes from "$lib/components/EntityNotes.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  const applicationId = $derived(page.params.id ?? "");
  let config = $state<GlassConfig>(loadConfig());
  const tokenMissing = $derived(operatorAuthMissing(config));
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">
      Application <CopyableCode value={applicationId} />
    </h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else}
    <EmptyState
      title="Application detail not yet built"
      description="Deep linking and browser back/forward already work for this route. The StageTracker and governed transition UI land in a later slice."
    />
    <EntityNotes {config} entityType="application" entityId={applicationId} />
  {/if}
</div>
