<script lang="ts">
  import { onMount } from "svelte";
  import { Button, Field, Panel } from "@ravenhelm/ui-svelte";

  import { createClient, loadConfig, saveConfig, type GlassConfig } from "$lib/client";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";

  // Connection panel lives here (Command home, `/`) because this is the
  // screen every session opens on (PRD section 5, workflow 9), and it is
  // the only place the operator token can be set — it must stay reachable
  // even though the rest of this route is a stub this slice.
  let config = $state<GlassConfig>(loadConfig());
  let checking = $state(false);
  let error = $state<unknown>(null);
  let lastCheckedAt = $state<string | null>(null);

  async function testConnection(): Promise<void> {
    checking = true;
    error = null;
    try {
      saveConfig(config);
      if (!config.token) {
        throw new Error("Operator token required (paste ULTRADEX_API_TOKEN).");
      }
      const client = createClient(config);
      await client.getHealth();
      lastCheckedAt = new Date().toLocaleTimeString();
    } catch (cause) {
      error = cause;
    } finally {
      checking = false;
    }
  }

  onMount(() => {
    void testConnection();
  });
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Command</h1>
    <p class="ccc-page-header__meta">Session orientation and connection setup.</p>
  </header>

  <Panel title="Connection" meta="local only">
    <p class="ccc-empty">
      Token = Ultradex API bearer (`ULTRADEX_API_TOKEN`). In 1Password:
      <em>Ultradex Local Obsidian Operator</em> → field <strong>operator token</strong>
      (not Dex, not the item password labeled credential unless they match).
    </p>
    <div class="ccc-grid ccc-grid--two" style="margin-top: 0.75rem">
      <Field
        label="API base URL (use this glass origin to proxy)"
        bind:value={config.baseUrl}
      />
      <Field
        label="Operator token (ULTRADEX_API_TOKEN)"
        type="password"
        autocomplete="off"
        bind:value={config.token}
      />
    </div>
    <div class="ccc-actions" style="margin-top: 0.75rem">
      <Button variant="primary" onclick={() => void testConnection()} disabled={checking}>
        {checking ? "Checking…" : "Save & test connection"}
      </Button>
      {#if lastCheckedAt && !error}
        <span class="ccc-empty">Last OK: {lastCheckedAt}</span>
      {/if}
    </div>
    {#if error}
      <div style="margin-top: 0.75rem">
        <ErrorBanner {error} />
      </div>
    {/if}
  </Panel>

  <!--
    TODO(FR-CMD-1..5): cross-entity roll-up — independent per-section load
    and failure (FR-CMD-1), freshness strip covering only the 4 real
    projections with Operation.freshness explicitly excluded (FR-CMD-2),
    Needs Attention rail ordering (FR-CMD-3), the past-nextActionAt rule
    (FR-CMD-4, unfireable today but unit-tested), and the single centered
    empty state on a fresh install (FR-CMD-5). The prior "What's Next"
    placeholder (lib/whats-next.ts) is superseded by this design; it is left
    in place, untouched, for the next slice to reuse or retire.
  -->
  <EmptyState
    title="Command roll-up not yet built"
    description="Freshness strip, Needs Attention rail, and Recent Activity land in a later slice (FR-CMD-1..5). Opportunities and Relationships are live via the section nav."
  />
</div>
