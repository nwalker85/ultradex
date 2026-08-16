<script lang="ts">
  import { page } from "$app/state";

  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";

  const outreachId = $derived(page.params.id ?? "");
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">
      Outreach <CopyableCode value={outreachId} />
    </h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  <!--
    TODO(FR-OUT-1..9): prepare / approve / send composer, message review
    with hash-verified / mismatch / not-found states (FR-OUT-9),
    ApprovalCountdown (FR-OUT-5), send enablement bound to the countdown
    selector never bare status (FR-OUT-6, risk G1). outreach_item(id) [BE-1]
    with listOutreach fallback.
  -->
  <EmptyState
    title="Outreach detail not yet built"
    description="Deep linking and browser back/forward already work for this route. Prepare, approve, and send composers land in a later slice."
  />
</div>
