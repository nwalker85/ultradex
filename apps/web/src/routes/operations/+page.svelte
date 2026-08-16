<script lang="ts">
  import EmptyState from "$lib/components/EmptyState.svelte";
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Operations</h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  <!--
    TODO(FR-OPS-1..9, FR-GW-1..8): this is where the governed-write pattern
    is built and tested in isolation (PRD section 7). This slice ships only
    FR-GW-6 (error-detail bug, fixed via lib/errors.ts + ErrorBanner,
    already reused everywhere) — CCC-only default filter (FR-OPS-1), limit
    select not cursor pagination (FR-OPS-2), refused rendered warning not
    danger (FR-OPS-3), both reason-code vocabularies visible together
    (FR-OPS-4), canned copy for the four *_unbound codes (FR-OPS-5),
    proofStatus as plain text with no lock/shield iconography (FR-OPS-6),
    cryptographic detail collapsed by default (FR-OPS-7), session-scoped
    History tabs labeled honestly (FR-OPS-8), 503-as-terminal-failed with no
    polling loop (FR-OPS-9) all land with the real screen.
  -->
  <EmptyState
    title="Activity browser not yet built"
    description="listOperations binding, the CCC-only filter, and receipt detail land in a later slice."
  />
</div>
