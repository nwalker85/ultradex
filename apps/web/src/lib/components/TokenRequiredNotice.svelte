<script lang="ts">
  import { Banner } from "@ravenhelm/ui-svelte";

  /**
   * A missing operator token is a client-side precondition, not a server
   * error — it must never route through ErrorBanner/normalizeError (that
   * machinery is for things Ultradex told us, and previously rendered a
   * spurious "Structured detail (unknown)" disclosure for this exact case).
   * This is a plain, calm notice with a link to where the token is set.
   */
</script>

<Banner tone="info">
  <p class="ccc-token-required">
    Operator token required — set it in <a href="/settings">Settings</a>.
  </p>
</Banner>

<style>
  .ccc-token-required {
    margin: 0;
  }
</style>
