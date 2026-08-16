<script lang="ts">
  import EmptyState from "$lib/components/EmptyState.svelte";
</script>

<!--
  No LeftNav item for this route per PRD section 7 ("(no nav item)") — it is
  reachable only by direct navigation, matching the current backend reality
  that sources.ingest always refuses.
-->
<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Sources</h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  <!--
    TODO(FR-SRC-1,2): session-local attempt list explicitly labeled "not
    from Ultradex" — there is no query that lists past ingests (FR-SRC-1);
    always refuses today with source_adapter_unbound, standard canned-copy
    treatment (FR-SRC-2).
  -->
  <EmptyState
    title="Source ingest not yet built"
    description="sources.ingest refuses today with source_adapter_unbound (no bound source connector, PRD section 2.4). This route has no nav item and is reached only by direct navigation."
  />
</div>
