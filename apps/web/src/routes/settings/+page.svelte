<script lang="ts">
  import { Button, Field, Panel } from "@ravenhelm/ui-svelte";

  import { createClient, loadConfig, saveConfig, type GlassConfig } from "$lib/client";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";

  let config = $state<GlassConfig>(loadConfig());
  let checking = $state(false);
  let connectionError = $state<unknown>(null);
  let lastCheckedAt = $state<string | null>(null);

  async function testConnection(): Promise<void> {
    checking = true;
    connectionError = null;
    try {
      saveConfig(config);
      const client = createClient(config);
      await client.getHealth();
      lastCheckedAt = new Date().toLocaleTimeString();
    } catch (cause) {
      connectionError = cause;
    } finally {
      checking = false;
    }
  }
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Settings</h1>
    <p class="ccc-page-header__meta">
      One-time operator connection. Same-origin traffic uses the deployed token.
    </p>
  </header>

  <Panel title="Connection" meta="admin">
    <p class="ccc-empty">
      On this host the glass proxy injects the operator bearer from 1Password
      (<em>Ultradex Local Obsidian Operator</em> → <strong>operator token</strong>).
      Leave the token blank unless you point the glass at a different API.
    </p>
    <div class="ccc-grid ccc-grid--two" style="margin-top: 0.75rem">
      <Field
        label="API base URL (this glass origin uses the proxy)"
        bind:value={config.baseUrl}
      />
      <Field
        label="Operator token override (optional)"
        type="password"
        autocomplete="off"
        bind:value={config.token}
      />
    </div>
    <div class="ccc-actions" style="margin-top: 0.75rem">
      <Button variant="primary" onclick={() => void testConnection()} disabled={checking}>
        {checking ? "Checking…" : "Save & test connection"}
      </Button>
      {#if lastCheckedAt && !connectionError}
        <span class="ccc-empty">Last OK: {lastCheckedAt}</span>
      {/if}
    </div>
    {#if connectionError}
      <div style="margin-top: 0.75rem">
        <ErrorBanner error={connectionError} />
      </div>
    {/if}
  </Panel>
</div>
