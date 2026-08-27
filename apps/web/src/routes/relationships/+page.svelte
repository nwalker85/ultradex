<script lang="ts">
  import { onMount } from "svelte";
  import { Badge, Field, Panel, Table } from "@ravenhelm/ui-svelte";
  import type { Contact, Opportunity, Relationship } from "@ultradex/sdk";

  import {
    createClient,
    loadConfig,
    operatorAuthMissing,
    saveConfig,
    type GlassConfig,
  } from "$lib/client";
  import { findOpportunityById } from "$lib/opportunities";
  import {
    buildRelationshipDisplay,
    dexRefToContactId,
    dedupeRelationshipDisplaysByContact,
    filterRelationshipDisplays,
    relevanceScoreTone,
    relationshipsEmptyState,
  } from "$lib/relationships";
  import { freshnessLabel } from "$lib/whats-next";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<unknown>(null);
  let relationships = $state<Relationship[]>([]);
  let contactsById = $state<Map<string, Contact>>(new Map());
  let opportunitiesById = $state<Map<string, Opportunity>>(new Map());
  let freshness = $state<string>("—");
  let search = $state("");

  const tokenMissing = $derived(operatorAuthMissing(config));
  const displays = $derived(
    dedupeRelationshipDisplaysByContact(
      relationships.map((relationship) =>
        buildRelationshipDisplay(
          relationship,
          contactsById.get(dexRefToContactId(relationship.dexContactRef)) ?? null,
          findOpportunityById(
            [...opportunitiesById.values()],
            relationship.opportunityId,
          ),
        ),
      ),
    ),
  );
  const filtered = $derived(filterRelationshipDisplays(displays, search));
  const emptyState = $derived(relationshipsEmptyState(search.trim() !== ""));

  async function refresh(): Promise<void> {
    saveConfig(config);
    if (tokenMissing) {
      return;
    }
    loading = true;
    error = null;
    try {
      const client = createClient(config);
      const [relPage, oppPage] = await Promise.all([
        client.listRelationships({ first: 50 }),
        client.listOpportunities({ first: 100 }),
      ]);
      relationships = [...relPage.items];
      freshness = freshnessLabel(relPage.freshness);

      const oppMap = new Map<string, Opportunity>();
      for (const opp of oppPage.items) {
        oppMap.set(opp.opportunityId, opp);
      }
      opportunitiesById = oppMap;

      const contactIds = [
        ...new Set(relationships.map((rel) => dexRefToContactId(rel.dexContactRef))),
      ];
      const contactResults = await Promise.all(
        contactIds.map((id) => client.getContact(id)),
      );
      const contactMap = new Map<string, Contact>();
      for (const contact of contactResults) {
        if (contact) {
          contactMap.set(contact.id, contact);
        }
      }
      contactsById = contactMap;
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
      People connected to opportunities — open a row for context, relevance, and
      linked pipeline records.
    </p>
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else}
    <Panel title="Relationships" meta={freshness}>
      <div class="ccc-actions" style="margin-bottom: 0.75rem">
        <Field
          label="Search"
          placeholder="Name, organization, role…"
          bind:value={search}
        />
      </div>

      {#if error}
        <ErrorBanner {error} />
      {:else if loading && relationships.length === 0}
        <p class="ccc-empty">Loading…</p>
      {:else if filtered.length === 0}
        <EmptyState title={emptyState.title} description={emptyState.description} />
      {:else}
        <Table columns={["Name", "Organization", "Role", "Fit"]} caption="Relationships">
          {#each filtered as row (row.relationship.relationshipId)}
            <tr>
              <th scope="row">
                <a href={`/relationships/${row.relationship.relationshipId}`}>
                  <strong>{row.name}</strong>
                </a>
              </th>
              <td>{row.organization ?? "—"}</td>
              <td>{row.role ?? "—"}</td>
              <td>
                {#if row.relationship.relevanceScore !== null}
                  <Badge tone={relevanceScoreTone(row.relationship.relevanceScore)}>
                    {Math.round(row.relationship.relevanceScore)}
                  </Badge>
                {:else}
                  —
                {/if}
              </td>
            </tr>
          {/each}
        </Table>
      {/if}
    </Panel>
  {/if}
</div>
