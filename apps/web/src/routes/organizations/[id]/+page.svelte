<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import { Badge, Panel, Table } from "@ravenhelm/ui-svelte";
  import type { Opportunity, Organization } from "@ultradex/sdk";

  import {
    createClient,
    loadConfig,
    operatorAuthMissing,
    saveConfig,
    type GlassConfig,
  } from "$lib/client";
  import { formatAdvocacyRating, advocacyTone } from "$lib/organizations";
  import CopyableCode from "$lib/components/CopyableCode.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import EntityNotes from "$lib/components/EntityNotes.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  const organizationId = $derived(page.params.id ?? "");

  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<unknown>(null);
  let organization = $state<Organization | null>(null);
  let opportunities = $state<Opportunity[]>([]);
  let notFound = $state(false);

  const tokenMissing = $derived(operatorAuthMissing(config));

  async function load(): Promise<void> {
    saveConfig(config);
    if (tokenMissing) {
      return;
    }
    loading = true;
    error = null;
    notFound = false;
    organization = null;
    opportunities = [];
    try {
      const client = createClient(config);
      const [org, oppPage] = await Promise.all([
        client.getOrganization(organizationId),
        client.listOpportunities({ first: 100, organizationId }),
      ]);
      if (org === null) {
        notFound = true;
        return;
      }
      organization = org;
      opportunities = [...oppPage.items];
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
      Organization <CopyableCode value={organizationId} />
    </h1>
    <p class="ccc-page-header__meta">Employer profile and linked opportunities.</p>
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else if error}
    <ErrorBanner {error} />
  {:else if loading && organization === null}
    <p class="ccc-empty">Loading…</p>
  {:else if notFound}
    <EmptyState
      title="Organization not found"
      description="No organization with this id exists in the directory."
    />
  {:else if organization}
    <Panel title={organization.name}>
      <dl class="ccc-detail-grid">
        <dt>Domain</dt>
        <dd>{organization.domain ?? "—"}</dd>
        <dt>Industry</dt>
        <dd>{organization.industry ?? "—"}</dd>
        <dt>Size</dt>
        <dd>{organization.size ?? "—"}</dd>
        <dt>Advocacy</dt>
        <dd>
          <Badge tone={advocacyTone(organization.advocacyRating)}>
            {formatAdvocacyRating(organization.advocacyRating)}
          </Badge>
        </dd>
        <dt>Notes</dt>
        <dd>{organization.notes ?? "—"}</dd>
      </dl>
    </Panel>

    <Panel title="Opportunities" meta={`${opportunities.length} at this organization`}>
      {#if opportunities.length === 0}
        <p class="ccc-empty">No opportunities linked yet.</p>
      {:else}
        <Table columns={["Role", "Status", "Score"]} caption="Opportunities at organization">
          {#each opportunities as opportunity (opportunity.opportunityId)}
            <tr>
              <th scope="row">
                <a href={`/opportunities/${opportunity.opportunityId}`}>
                  <strong>{opportunity.title}</strong>
                </a>
              </th>
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

    <EntityNotes {config} entityType="organization" entityId={organization.id} />
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
</style>
