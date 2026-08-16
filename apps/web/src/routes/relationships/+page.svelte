<script lang="ts">
  import { onMount } from "svelte";
  import { Panel, Table } from "@ravenhelm/ui-svelte";
  import type { Relationship } from "@ultradex/sdk";

  import { createClient, loadConfig, saveConfig, type GlassConfig } from "$lib/client";
  import { freshnessLabel } from "$lib/whats-next";
  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";

  // Moved from the former single-route `+page.svelte` — same data-loading
  // behavior (listRelationships, first: 50) as before the routing
  // migration.
  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<unknown>(null);
  let relationships = $state<Relationship[]>([]);
  let freshness = $state<string>("—");

  async function refresh(): Promise<void> {
    loading = true;
    error = null;
    try {
      saveConfig(config);
      if (!config.token) {
        throw new Error("Operator token required — set it on Command (`/`).");
      }
      const client = createClient(config);
      const page = await client.listRelationships({ first: 50 });
      relationships = [...page.items];
      freshness = freshnessLabel(page.freshness);
    } catch (cause) {
      error = cause;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void refresh();
  });
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Relationships</h1>
    <p class="ccc-page-header__meta">
      List projection — split view and deep-linked detail land in a later
      slice.
    </p>
  </header>

  <!--
    TODO(FR-REL-1,2): split view with `?open=<id>` deep link (FR-REL-1); no
    bare "New relationship" entry point — relationships.sync requires an
    opportunityId, so creation only enters from an Opportunity's Related tab
    (FR-REL-2). This screen currently ports forward only the existing
    read-and-list behavior.
  -->
  <Panel title="Relationships" meta={freshness}>
    {#if error}
      <ErrorBanner {error} />
    {:else if relationships.length === 0}
      <p class="ccc-empty">
        {loading ? "Loading…" : "No relationships in projection."}
      </p>
    {:else}
      <Table columns={["Contact", "Opportunity", "Context"]} caption="Relationships">
        {#each relationships.slice(0, 12) as relationship}
          <tr>
            <th scope="row">{relationship.dexContactRef}</th>
            <td><CopyableCode value={relationship.opportunityId} /></td>
            <td>{relationship.relevanceSummary ?? "—"}</td>
          </tr>
        {/each}
      </Table>
    {/if}
  </Panel>
</div>
