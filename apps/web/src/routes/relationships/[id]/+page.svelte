<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import { Badge, Panel } from "@ravenhelm/ui-svelte";
  import type { Contact, Opportunity, Relationship } from "@ultradex/sdk";

  import {
    createClient,
    loadConfig,
    operatorAuthMissing,
    saveConfig,
    type GlassConfig,
  } from "$lib/client";
  import { relationshipTierTone } from "$lib/contacts";
  import {
    buildRelationshipDisplay,
    dexRefToContactId,
    relevanceScoreTone,
  } from "$lib/relationships";
  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import FreshnessTag from "$lib/components/FreshnessTag.svelte";
  import EntityNotes from "$lib/components/EntityNotes.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  const relationshipId = $derived(page.params.id ?? "");

  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<unknown>(null);
  let relationship = $state<Relationship | null>(null);
  let contact = $state<Contact | null>(null);
  let opportunity = $state<Opportunity | null>(null);
  let notFound = $state(false);

  const tokenMissing = $derived(operatorAuthMissing(config));
  const display = $derived(
    relationship
      ? buildRelationshipDisplay(relationship, contact, opportunity)
      : null,
  );

  async function load(): Promise<void> {
    saveConfig(config);
    if (tokenMissing) {
      return;
    }
    loading = true;
    error = null;
    notFound = false;
    relationship = null;
    contact = null;
    opportunity = null;
    try {
      const client = createClient(config);
      const found = await client.getRelationship(relationshipId);
      if (found === null) {
        notFound = true;
        return;
      }
      relationship = found;
      const [loadedContact, loadedOpportunity] = await Promise.all([
        client.getContact(dexRefToContactId(found.dexContactRef)),
        client.getOpportunity(found.opportunityId),
      ]);
      contact = loadedContact;
      opportunity = loadedOpportunity;
    } catch (cause) {
      error = cause;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void load();
  });
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <p class="ccc-page-header__meta"><a href="/relationships">← Relationships</a></p>
    <h1 class="ccc-page-header__title">
      {#if display}
        {display.name}
      {:else}
        Relationship
      {/if}
    </h1>
    {#if display?.role || display?.organization}
      <p class="ccc-page-header__meta">
        {#if display.role}{display.role}{/if}
        {#if display.role && display.organization} · {/if}
        {#if display.organization}{display.organization}{/if}
      </p>
    {/if}
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else if loading}
    <p class="ccc-empty">Loading…</p>
  {:else if error}
    <ErrorBanner {error} />
  {:else if notFound}
    <EmptyState
      title="Relationship not found"
      description="This id is not in the current projection page. It may have been removed or is beyond the fetched window."
    />
  {:else if relationship && display}
    <div class="ccc-grid ccc-grid--two">
      <Panel title="Contact">
        {#if contact}
          <dl class="ccc-detail-list">
            <div><dt>Name</dt><dd>{contact.name}</dd></div>
            <div><dt>Organization</dt><dd>{contact.company ?? "—"}</dd></div>
            <div><dt>Role</dt><dd>{contact.jobTitle ?? "—"}</dd></div>
            <div><dt>Email</dt><dd>{contact.email ?? "—"}</dd></div>
            {#if contact.relationshipTier}
              <div>
                <dt>Tier</dt>
                <dd>
                  <Badge tone={relationshipTierTone(contact.relationshipTier)}>
                    {contact.relationshipTier}
                  </Badge>
                </dd>
              </div>
            {/if}
            {#if contact.advocacyScore !== null}
              <div><dt>Advocacy</dt><dd>{Math.round(contact.advocacyScore)}</dd></div>
            {/if}
            {#if contact.notes}
              <div><dt>Legacy notes</dt><dd>{contact.notes}</dd></div>
            {/if}
          </dl>
        {:else}
          <dl class="ccc-detail-list">
            <div><dt>Name</dt><dd>{display.name}</dd></div>
            <div><dt>Organization</dt><dd>{display.organization ?? "—"}</dd></div>
            <div><dt>Role</dt><dd>{display.role ?? "—"}</dd></div>
            <div><dt>Dex ref</dt><dd><CopyableCode value={relationship.dexContactRef} /></dd></div>
          </dl>
        {/if}
      </Panel>

      <Panel title="Pipeline link">
        {#if opportunity}
          <p>
            <a href={`/opportunities/${opportunity.opportunityId}`}>
              <strong>{opportunity.employer}</strong> — {opportunity.title}
            </a>
          </p>
        {:else}
          <p class="ccc-empty">Opportunity <CopyableCode value={relationship.opportunityId} /></p>
        {/if}
        <dl class="ccc-detail-list">
          <div>
            <dt>Relevance</dt>
            <dd>
              {#if relationship.relevanceScore !== null}
                <Badge tone={relevanceScoreTone(relationship.relevanceScore)}>
                  {Math.round(relationship.relevanceScore)}
                </Badge>
              {:else}
                —
              {/if}
            </dd>
          </div>
          {#if relationship.relevanceSummary}
            <div><dt>Context</dt><dd>{relationship.relevanceSummary}</dd></div>
          {/if}
          <div><dt>Freshness</dt><dd><FreshnessTag freshness={relationship.freshness} /></dd></div>
        </dl>
      </Panel>
    </div>
    <EntityNotes
      {config}
      entityType="relationship"
      entityId={relationship.relationshipId}
    />
    {#if contact}
      <EntityNotes
        {config}
        entityType="contact"
        entityId={contact.id}
        title="Contact notes"
      />
    {/if}

  {/if}
</div>

<style>
  .ccc-detail-list {
    display: grid;
    gap: 0.75rem;
    margin: 0;
  }

  .ccc-detail-list div {
    display: grid;
    gap: 0.15rem;
  }

  .ccc-detail-list dt {
    color: var(--rh-muted);
    font-size: var(--rh-typography-size-body-small);
    margin: 0;
  }

  .ccc-detail-list dd {
    margin: 0;
  }
</style>
