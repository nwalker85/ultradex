<script lang="ts">
  import { onMount } from "svelte";
  import { Badge, Field, Panel, Table } from "@ravenhelm/ui-svelte";
  import type { Organization } from "@ultradex/sdk";

  import {
    createClient,
    loadConfig,
    operatorAuthMissing,
    saveConfig,
    type GlassConfig,
  } from "$lib/client";
  import {
    advocacyTone,
    filterOrganizations,
    formatAdvocacyRating,
    organizationsEmptyState,
    sortOrganizations,
    type OrganizationSortField,
  } from "$lib/organizations";
  import { freshnessLabel } from "$lib/whats-next";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  let config = $state<GlassConfig>(loadConfig());
  let loading = $state(false);
  let error = $state<unknown>(null);
  let organizations = $state<Organization[]>([]);
  let freshness = $state<string>("—");
  let search = $state("");
  let sortBy = $state<OrganizationSortField>("name");

  const tokenMissing = $derived(operatorAuthMissing(config));
  const filtered = $derived(
    sortOrganizations(filterOrganizations(organizations, search), sortBy),
  );
  const emptyState = $derived(organizationsEmptyState(search.trim() !== ""));

  async function refresh(): Promise<void> {
    saveConfig(config);
    if (tokenMissing) {
      return;
    }
    loading = true;
    error = null;
    try {
      const client = createClient(config);
      const page = await client.getOrganizations({ first: 100, sortBy: "name" });
      organizations = [...page.items];
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
    <h1 class="ccc-page-header__title">Organizations</h1>
    <p class="ccc-page-header__meta">
      Employer directory — contacts, leads, and opportunities roll up here.
    </p>
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else if error}
    <ErrorBanner {error} />
  {:else}
    <Panel title="Employers" meta={freshness}>
      <div class="ccc-actions" style="margin-bottom: 0.75rem; gap: 0.75rem">
        <Field label="Search">
          <input
            class="ccc-input"
            type="search"
            placeholder="Name, domain, industry…"
            bind:value={search}
          />
        </Field>
        <Field label="Sort">
          <select class="ccc-input" bind:value={sortBy}>
            <option value="name">Name</option>
            <option value="advocacy">Advocacy</option>
            <option value="size">Size</option>
          </select>
        </Field>
      </div>

      {#if loading && organizations.length === 0}
        <p class="ccc-empty">Loading…</p>
      {:else if filtered.length === 0}
        <EmptyState title={emptyState.title} description={emptyState.description} />
      {:else}
        <Table columns={["Organization", "Domain", "Industry", "Advocacy"]} caption="Organizations">
          {#each filtered as org (org.id)}
            <tr>
              <th scope="row">
                <a href={`/organizations/${org.id}`}><strong>{org.name}</strong></a>
              </th>
              <td>{org.domain ?? "—"}</td>
              <td>{org.industry ?? "—"}</td>
              <td>
                <Badge tone={advocacyTone(org.advocacyRating)}>
                  {formatAdvocacyRating(org.advocacyRating)}
                </Badge>
              </td>
            </tr>
          {/each}
        </Table>
      {/if}
    </Panel>
  {/if}
</div>
