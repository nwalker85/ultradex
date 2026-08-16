<script lang="ts">
  import { page } from "$app/state";

  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";

  const applicationId = $derived(page.params.id ?? "");
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">
      Application <CopyableCode value={applicationId} />
    </h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  <!--
    TODO(FR-APP-1..6): StageTracker, stage history/artifacts/next-action,
    application(id) [BE-1] with listApplications fallback. Not e2e
    verifiable until BE-6 lands (FR-APP-5) since no command originates a
    row today.
  -->
  <EmptyState
    title="Application detail not yet built"
    description="Deep linking and browser back/forward already work for this route. The StageTracker and governed transition UI land in a later slice."
  />
</div>
