<script lang="ts">
  import EmptyState from "$lib/components/EmptyState.svelte";
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Applications</h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  <!--
    TODO(FR-APP-1..6): stage-grouped table, not a kanban (FR-APP-1, OOS-1);
    honest empty state naming BE-6 as the real cause with no fake "New
    application" button (FR-APP-2); client-side opportunity join degrading
    to the raw id (FR-APP-3); every stage pill through the governed-write
    pattern (FR-APP-4); e2e verification gated on BE-6 (FR-APP-5);
    structurally-empty tabs labeled honestly (FR-APP-6). listApplications
    binding lands with the real screen.
  -->
  <EmptyState
    title="No command originates an Application yet"
    description="applications.create does not exist in Ultradex today (PRD section 11.3, BE-6). This route is a placeholder; the stage-grouped list and governed transitions land in a later slice."
  />
</div>
