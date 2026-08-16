<script lang="ts">
  import { page } from "$app/state";

  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";

  const operationId = $derived(page.params.id ?? "");
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">
      Operation <CopyableCode value={operationId} />
    </h1>
    <p class="ccc-page-header__meta">Routing foundation slice — screen not yet built.</p>
  </header>

  <!--
    TODO(FR-OPS-*, section 8.2): getOperation status, getOperationEvents
    timeline with collapsed payload disclosures, getExecutionReceipt with
    proofStatus shown plainly (no lock/shield iconography, FR-OPS-6) and
    cryptographic detail collapsed by default (FR-OPS-7).
  -->
  <EmptyState
    title="Operation detail not yet built"
    description="Deep linking and browser back/forward already work for this route. Status, event timeline, and receipt land in a later slice."
  />
</div>
