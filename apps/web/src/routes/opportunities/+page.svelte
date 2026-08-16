<script lang="ts">
  import { onMount } from "svelte";
  import { Button, Panel, Select, Table } from "@ravenhelm/ui-svelte";
  import type { Opportunity } from "@ultradex/sdk";

  import { createClient, loadConfig, saveConfig, type GlassConfig } from "$lib/client";
  import { freshnessLabel } from "$lib/whats-next";
  import {
    OPPORTUNITY_STATUS_FILTERS,
    opportunitiesEmptyState,
    type OpportunityStatusFilter,
  } from "$lib/opportunities";
  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import CreateOpportunityComposer from "$lib/components/CreateOpportunityComposer.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<unknown>(null);
  let opportunities = $state<Opportunity[]>([]);
  let freshness = $state<string>("—");
  let statusFilter = $state<OpportunityStatusFilter>("");
  let showCreate = $state(false);

  // Task 1 fix — a missing token is a client-side precondition, not a
  // server error. It never becomes `error` / never routes through
  // ErrorBanner's structured-detail machinery; it renders a plain, calm
  // notice instead (TokenRequiredNotice), and no request is attempted.
  const tokenMissing = $derived(config.token.trim() === "");
  const client = $derived(tokenMissing ? null : createClient(config));
  const emptyState = $derived(opportunitiesEmptyState(statusFilter));

  const statusOptions = [
    { value: "", label: "All statuses" },
    ...OPPORTUNITY_STATUS_FILTERS.map((status) => ({ value: status, label: status })),
  ];

  async function refresh(): Promise<void> {
    saveConfig(config);
    if (tokenMissing) {
      return;
    }
    loading = true;
    error = null;
    try {
      const activeClient = createClient(config);
      const page = await activeClient.listOpportunities({
        first: 50,
        ...(statusFilter === "" ? {} : { status: statusFilter }),
      });
      opportunities = [...page.items];
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
    <h1 class="ccc-page-header__title">Opportunities</h1>
    <p class="ccc-page-header__meta">
      List projection with a real status filter, create composer, and detail links.
    </p>
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else}
    <Panel title="Opportunities" meta={freshness}>
      <div class="ccc-actions" style="margin-bottom: 0.75rem; justify-content: space-between">
        <Select
          label="Status"
          options={statusOptions}
          bind:value={statusFilter}
          onchange={() => void refresh()}
        />
        <Button variant="primary" onclick={() => (showCreate = !showCreate)}>
          {showCreate ? "Close" : "New opportunity"}
        </Button>
      </div>

      {#if showCreate && client}
        <div class="ccc-create-opportunity-panel">
          <CreateOpportunityComposer
            {client}
            onCreated={() => {
              void refresh();
            }}
          />
        </div>
      {/if}

      {#if error}
        <ErrorBanner {error} />
      {:else if loading && opportunities.length === 0}
        <p class="ccc-empty">Loading…</p>
      {:else if opportunities.length === 0}
        <EmptyState title={emptyState.title} description={emptyState.description}>
          {#if emptyState.kind === "true-zero"}
            <Button variant="primary" onclick={() => (showCreate = true)}>Create opportunity</Button>
          {:else}
            <Button
              onclick={() => {
                statusFilter = "";
                void refresh();
              }}
            >
              Clear filter
            </Button>
          {/if}
        </EmptyState>
      {:else}
        <Table columns={["Employer / role", "ID", "State", "Fit"]} caption="Opportunities">
          {#each opportunities as opportunity (opportunity.opportunityId)}
            <tr>
              <th scope="row">
                <a href={`/opportunities/${opportunity.opportunityId}`}>
                  <strong>{opportunity.employer}</strong>
                </a><br />
                <span class="ccc-empty">{opportunity.title}</span>
              </th>
              <td><CopyableCode value={opportunity.opportunityId} /></td>
              <td>{opportunity.status}</td>
              <td>
                {opportunity.fitScore === null
                  ? "Not scored"
                  : `${Math.round(opportunity.fitScore)} / 100`}
              </td>
            </tr>
          {/each}
        </Table>
      {/if}
    </Panel>
  {/if}
</div>

<style>
  .ccc-create-opportunity-panel {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    margin-bottom: var(--rh-space-16);
    padding: var(--rh-space-16);
  }
</style>
