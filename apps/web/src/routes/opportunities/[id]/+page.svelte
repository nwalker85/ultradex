<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import { Badge, Panel } from "@ravenhelm/ui-svelte";
  import type { Opportunity } from "@ultradex/sdk";

  import {
    createClient,
    loadConfig,
    operatorAuthMissing,
    saveConfig,
    type GlassConfig,
  } from "$lib/client";
  import { findOpportunityById } from "$lib/opportunities";
  import { isExcludedOpportunity } from "$lib/opportunity-ranking";
  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import FreshnessTag from "$lib/components/FreshnessTag.svelte";
  import ScoreOpportunityAction from "$lib/components/ScoreOpportunityAction.svelte";
  import SyncRelationshipAction from "$lib/components/SyncRelationshipAction.svelte";
  import EntityNotes from "$lib/components/EntityNotes.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  const opportunityId = $derived(page.params.id ?? "");

  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<unknown>(null);
  let opportunity = $state<Opportunity | null>(null);
  let notFound = $state(false);

  const tokenMissing = $derived(operatorAuthMissing(config));
  const client = $derived(tokenMissing ? null : createClient(config));
  // Lane G item 3 — "Why this score" only renders once the scorer has
  // actually run (fitScore or fitExplanation present); never for a
  // genuinely unscored opportunity.
  const hasScore = $derived(
    opportunity !== null && (opportunity.fitScore !== null || opportunity.fitExplanation !== null),
  );
  const excluded = $derived(opportunity !== null && isExcludedOpportunity(opportunity));

  async function load(): Promise<void> {
    saveConfig(config);
    if (tokenMissing) {
      return;
    }
    loading = true;
    error = null;
    notFound = false;
    opportunity = null;
    try {
      const activeClient = createClient(config);
      // FR-OPP-3 (NFR-1) — the SDK does not wrap the server's
      // `opportunity(id)` field (BE-1). This is the documented fallback:
      // fetch a page and find the id client-side. It degrades past a few
      // hundred rows; the console warning below is the honest flag for
      // that, not a silent truncation.
      const listPage = await activeClient.listOpportunities({ first: 100 });
      if (import.meta.env.DEV && listPage.nextCursor !== null) {
        console.warn(
          "[opportunities/[id]] listOpportunities({first:100}) fallback has more rows than fetched " +
            "(nextCursor present) — this detail lookup can silently miss records past the first 100. " +
            "See FR-OPP-3 / NFR-1 / BE-1.",
        );
      }
      const found = findOpportunityById(listPage.items, opportunityId);
      if (found === null) {
        notFound = true;
      } else {
        opportunity = found;
      }
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
    <h1 class="ccc-page-header__title">
      Opportunity <CopyableCode value={opportunityId} />
    </h1>
    <p class="ccc-page-header__meta">Overview, evidence, and governed Score / Sync actions.</p>
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else if error}
    <ErrorBanner {error} />
  {:else if loading && opportunity === null}
    <p class="ccc-empty">Loading…</p>
  {:else if notFound}
    <EmptyState
      title="Opportunity not found"
      description="No opportunity with this id was found in the first 100 rows of the projection. It may not exist, or (FR-OPP-3/NFR-1) it may be past the client-side fallback's lookup window."
    />
  {:else if opportunity}
    <Panel title="Overview">
      <dl class="ccc-detail-grid">
        <dt>Employer</dt>
        <dd>{opportunity.employer}</dd>
        <dt>Title</dt>
        <dd>{opportunity.title}</dd>
        <dt>Status</dt>
        <dd><Badge tone="neutral">{opportunity.status}</Badge></dd>
        <dt>Score</dt>
        <dd>
          {opportunity.fitScore === null ? "Not scored" : `${Math.round(opportunity.fitScore)} / 100`}
          {#if excluded}
            <Badge tone="warning">excluded</Badge>
          {/if}
        </dd>
        <dt>Risk flags</dt>
        <dd>
          {#if opportunity.riskFlags.length === 0}
            None recorded.
          {:else}
            {#each opportunity.riskFlags as flag (flag)}
              <Badge tone="warning">{flag}</Badge>
            {/each}
          {/if}
        </dd>
        <dt>Location</dt>
        <!-- Permanently null today — an honest "not captured", never a blank cell or a fake value. -->
        <dd>{opportunity.location ?? "Not captured"}</dd>
        <dt>Role family</dt>
        <dd>{opportunity.roleFamily ?? "Not captured"}</dd>
        <dt>Freshness</dt>
        <dd><FreshnessTag freshness={opportunity.freshness} /></dd>
      </dl>
    </Panel>

    {#if hasScore}
      <!-- Lane G item 3 — "Why this score": full score_explanation, only
           rendered once the scorer has actually run. -->
      <Panel title="Why this score" meta={excluded ? "excluded employer" : undefined}>
        <p>
          <strong>{opportunity.fitScore === null ? "Not scored" : `${Math.round(opportunity.fitScore)} / 100`}</strong>
          {#if excluded}
            <Badge tone="warning">excluded</Badge>
          {/if}
        </p>
        <p class="ccc-empty">{opportunity.fitExplanation ?? "No explanation recorded."}</p>
      </Panel>
    {/if}

    <Panel title="Evidence" meta={`${opportunity.evidenceRefs.length} reference(s)`}>
      {#if opportunity.evidenceRefs.length === 0}
        <p class="ccc-empty">No evidence references recorded.</p>
      {:else}
        <div class="ccc-evidence-list">
          {#each opportunity.evidenceRefs as evidence (evidence.evidenceId)}
            <div class="ccc-evidence-item">
              <div class="ccc-evidence-item__header">
                <CopyableCode value={evidence.evidenceId} />
                <!-- FR-OPP-4 — classification renders whatever the API returns, never a hardcoded "private". -->
                <Badge tone="accent">{evidence.classification}</Badge>
                <span class="ccc-empty ccc-mono">{evidence.sourceKind}</span>
              </div>
              <!-- FR-EVID-2 — only redactedSummary renders as readable prose. -->
              <p class="ccc-evidence-item__summary">{evidence.redactedSummary}</p>
              <!-- FR-EVID-1 — sourceRef never appears as untruncated inline prose, only via CopyableCode. -->
              <p class="ccc-empty">
                Source ref: <CopyableCode value={evidence.sourceRef} />
              </p>
            </div>
          {/each}
        </div>
      {/if}
    </Panel>

    {#if client}
      <Panel title="Score" meta="deterministic Intent scorer">
        <ScoreOpportunityAction {client} opportunityId={opportunity.opportunityId} />
      </Panel>

      <Panel title="Sync relationship" meta="relationship_resolver_unbound today">
        <SyncRelationshipAction {client} opportunityId={opportunity.opportunityId} />
      </Panel>
    {/if}

    <EntityNotes
      {config}
      entityType="opportunity"
      entityId={opportunity.opportunityId}
    />
  {/if}
</div>

<style>
  .ccc-detail-grid {
    display: grid;
    gap: var(--rh-space-4) var(--rh-space-16);
    grid-template-columns: max-content 1fr;
    margin: 0;
  }

  .ccc-detail-grid dt {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }

  .ccc-detail-grid dd {
    margin: 0 0 var(--rh-space-8);
  }

  .ccc-evidence-list {
    display: grid;
    gap: var(--rh-space-12);
  }

  .ccc-evidence-item {
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    padding: var(--rh-space-12);
  }

  .ccc-evidence-item__header {
    align-items: center;
    display: flex;
    gap: var(--rh-space-8);
    margin-bottom: var(--rh-space-8);
  }

  .ccc-evidence-item__summary {
    margin: 0 0 var(--rh-space-8);
  }
</style>
