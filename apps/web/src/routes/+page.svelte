<script lang="ts">
  import { onMount } from "svelte";
  import {
    Badge,
    Banner,
    Button,
    Field,
    Panel,
    Select,
    Table,
  } from "@ravenhelm/ui-svelte";
  import type { Opportunity, Relationship } from "@ultradex/sdk";

  import { createClient, loadConfig, saveConfig, type GlassConfig } from "$lib/client";
  import { freshnessLabel, pickWhatsNext } from "$lib/whats-next";

  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<string | null>(null);
  let opportunities = $state<Opportunity[]>([]);
  let relationships = $state<Relationship[]>([]);
  let oppFreshness = $state<string>("—");
  let relFreshness = $state<string>("—");
  let selectedOpportunityId = $state("");

  const whatsNext = $derived(pickWhatsNext(opportunities, relationships));
  const opportunityChoices = $derived(
    opportunities
      .filter((item) => item.status !== "archived")
      .map((item) => ({
        value: item.opportunityId,
        label: `${item.employer} — ${item.title}`,
      })),
  );

  async function refresh(): Promise<void> {
    loading = true;
    error = null;
    try {
      saveConfig(config);
      if (!config.token) {
        throw new Error("Operator token required (paste ULTRADEX_API_TOKEN).");
      }
      const client = createClient(config);
      const [oppPage, relPage] = await Promise.all([
        client.listOpportunities({ first: 50 }),
        client.listRelationships({ first: 50 }),
      ]);
      opportunities = [...oppPage.items];
      relationships = [...relPage.items];
      oppFreshness = freshnessLabel(oppPage.freshness);
      relFreshness = freshnessLabel(relPage.freshness);
      if (
        selectedOpportunityId === "" &&
        opportunityChoices[0] !== undefined
      ) {
        selectedOpportunityId = opportunityChoices[0].value;
      }
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Refresh failed";
    } finally {
      loading = false;
    }
  }

  function copyId(value: string): void {
    void navigator.clipboard?.writeText(value);
  }

  onMount(() => {
    void refresh();
  });
</script>

<div class="ccc-shell">
  <section id="connection">
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
        <Button variant="primary" onclick={() => void refresh()} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh projections"}
        </Button>
      </div>
      {#if error}
        <div style="margin-top: 0.75rem">
          <Banner tone="danger">{error}</Banner>
        </div>
      {/if}
    </Panel>
  </section>

  <section id="whats-next">
    <Panel title="What's Next?" meta="Director stub">
      <Badge tone={whatsNext.kind !== "empty" ? "accent" : "neutral"}>{whatsNext.kind}</Badge>
      <h3 style="margin: 0.5rem 0 0.25rem">{whatsNext.title}</h3>
      <p class="ccc-empty">{whatsNext.reason}</p>
      {#if whatsNext.kind === "opportunity"}
        <p class="ccc-mono">
          {whatsNext.id}
          <Button variant="ghost" onclick={() => copyId(whatsNext.id)}>Copy ID</Button>
        </p>
      {/if}
    </Panel>
  </section>

  <div class="ccc-grid ccc-grid--two">
    <section id="opportunities">
      <Panel title="Opportunities" meta={oppFreshness}>
        {#if opportunities.length === 0}
          <p class="ccc-empty">No opportunities in projection.</p>
        {:else}
          <Table columns={["Employer / role", "ID", "State", "Fit"]} caption="Opportunities">
            {#each opportunities.filter((o) => o.status !== "archived") as opportunity}
              <tr>
                <th scope="row">
                  <strong>{opportunity.employer}</strong><br />
                  <span class="ccc-empty">{opportunity.title}</span>
                </th>
                <td>
                  <code>{opportunity.opportunityId}</code>
                  <Button
                    variant="ghost"
                    onclick={() => copyId(opportunity.opportunityId)}
                  >
                    Copy
                  </Button>
                </td>
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
    </section>

    <section id="relationships">
      <Panel title="Relationships" meta={relFreshness}>
        {#if relationships.length === 0}
          <p class="ccc-empty">No relationships in projection.</p>
        {:else}
          <Table
            columns={["Contact", "Opportunity", "Context"]}
            caption="Relationships"
          >
            {#each relationships.slice(0, 12) as relationship}
              <tr>
                <th scope="row">{relationship.dexContactRef}</th>
                <td><code>{relationship.opportunityId}</code></td>
                <td>{relationship.relevanceSummary ?? "—"}</td>
              </tr>
            {/each}
          </Table>
        {/if}
      </Panel>
    </section>
  </div>

  <Panel title="Score opportunity" meta="governed command prep">
    {#if opportunityChoices.length === 0}
      <p class="ccc-empty">Load opportunities to enable selection.</p>
    {:else}
      <Select
        label="Opportunity"
        options={opportunityChoices}
        bind:value={selectedOpportunityId}
      />
      <p class="ccc-mono" style="margin-top: 0.75rem">
        Selected ID: {selectedOpportunityId}
      </p>
      <Banner tone="info">
        Submit path stays on Ultradex v2 commands — wire Confirm in the next
        slice. ML scoring runs in the Python worker, not this glass.
      </Banner>
    {/if}
  </Panel>
</div>
