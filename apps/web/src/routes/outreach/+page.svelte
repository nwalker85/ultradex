<script lang="ts">
  import EmptyState from "$lib/components/EmptyState.svelte";
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Outreach</h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  <!--
    TODO(FR-OUT-1..9): client-side SubtleCrypto commitment (FR-OUT-1);
    localStorage draft cache with "this browser only" disclosure
    (FR-OUT-2); expiry-aware list badges via ApprovalCountdown (FR-OUT-3,
    FR-OUT-5); send enablement bound to the countdown selector, never bare
    status, with a regression test (FR-OUT-6, risk G1); verification
    checkbox gating send (FR-OUT-7); no cancel affordance until BE-7
    (FR-OUT-8); three distinct message-review states (FR-OUT-9).
    listOutreach binding lands with the real screen.
  -->
  <EmptyState
    title="Outreach list not yet built"
    description="0 outreach rows exist in Ultradex today (PRD section 2.2). The expiry-aware list and the governed prepare / approve / send flow land in a later slice."
  />
</div>
