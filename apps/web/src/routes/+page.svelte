<script lang="ts">
  import { onMount } from "svelte";
  import { Badge, Button, Field, Panel, Table } from "@ravenhelm/ui-svelte";
  import type {
    Application,
    ApplicationPage,
    Operation,
    OpportunityPage,
    OutreachPage,
    RelationshipPage,
  } from "@ultradex/sdk";

  import { createClient, loadConfig, saveConfig, type GlassConfig } from "$lib/client";
  import {
    buildFreshnessRollupInput,
    buildNeedsAttention,
    isCommandHomeFreshInstall,
    overdueApplications,
    rollupFreshness,
    type NeedsAttentionKind,
    type OutreachWithApprovalExpiry,
  } from "$lib/command-home";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import FreshnessTag from "$lib/components/FreshnessTag.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  // Connection panel lives here (Command home, `/`) because this is the
  // screen every session opens on (PRD section 5, workflow 9), and it is
  // the only place the operator token can be set — it must stay reachable
  // regardless of the roll-up's own load state below.
  let config = $state<GlassConfig>(loadConfig());
  let checking = $state(false);
  let connectionError = $state<unknown>(null);
  let lastCheckedAt = $state<string | null>(null);

  async function testConnection(): Promise<void> {
    checking = true;
    connectionError = null;
    try {
      saveConfig(config);
      if (!config.token) {
        throw new Error("Operator token required (paste ULTRADEX_API_TOKEN).");
      }
      const client = createClient(config);
      await client.getHealth();
      lastCheckedAt = new Date().toLocaleTimeString();
    } catch (cause) {
      connectionError = cause;
    } finally {
      checking = false;
    }
  }

  const tokenMissing = $derived(config.token.trim() === "");

  // ---------------------------------------------------------------------
  // FR-CMD-1 — four independent, mount-time section loads (PRD §7 screen
  // inventory: listOpportunities, listApplications, listOutreach,
  // listOperations). Each has its own loading/error/data state and its own
  // try/catch; a failure in one never touches the other three, and each
  // renders its own inline ErrorBanner instead of taking down the page.
  // ---------------------------------------------------------------------

  let oppLoading = $state(false);
  let oppError = $state<unknown>(null);
  let oppAttempted = $state(false);
  let oppPage = $state<OpportunityPage | null>(null);

  let appLoading = $state(false);
  let appError = $state<unknown>(null);
  let applicationsPage = $state<ApplicationPage | null>(null);

  let outLoading = $state(false);
  let outError = $state<unknown>(null);
  let outreachPage = $state<OutreachPage | null>(null);
  let outreachWithExpiry = $state<OutreachWithApprovalExpiry[]>([]);

  // Relationships — loaded ONLY for its page-level freshness (FR-CMD-2,
  // supervisor decision 2026-08-15: it's the ~2242-contact projection the
  // ambient Dex sweep feeds, so its staleness is exactly what the strip
  // exists to surface). No Relationships section renders on this page and
  // no relationship rows feed the Needs Attention rail — fetched at the
  // smallest page the SDK allows (`first: 1`) since only `.freshness` is
  // read.
  let relLoading = $state(false);
  let relError = $state<unknown>(null);
  let relationshipsPage = $state<RelationshipPage | null>(null);

  let opsLoading = $state(false);
  let opsError = $state<unknown>(null);
  let opsAttempted = $state(false);
  let operations = $state<Operation[]>([]);

  async function loadOpportunities(): Promise<void> {
    if (tokenMissing) {
      return;
    }
    oppLoading = true;
    oppError = null;
    try {
      const client = createClient(config);
      oppPage = await client.listOpportunities({ first: 50 });
    } catch (cause) {
      oppError = cause;
    } finally {
      oppLoading = false;
      oppAttempted = true;
    }
  }

  async function loadApplications(): Promise<void> {
    if (tokenMissing) {
      return;
    }
    appLoading = true;
    appError = null;
    try {
      const client = createClient(config);
      applicationsPage = await client.listApplications({ first: 50 });
    } catch (cause) {
      appError = cause;
    } finally {
      appLoading = false;
    }
  }

  async function loadOutreach(): Promise<void> {
    if (tokenMissing) {
      return;
    }
    outLoading = true;
    outError = null;
    try {
      const client = createClient(config);
      const page = await client.listOutreach({ first: 50 });
      outreachPage = page;
      // FR-CMD-3 — resolve each `approved` item's real expiry from its
      // approval contract (Outreach itself has no expiresAt field). This
      // is a best-effort join scoped to the Outreach section only: a
      // failed lookup degrades that one item out of the expiring-soon
      // bucket rather than failing the whole section (FR-CMD-1 scopes
      // fault isolation to the four primary calls, not to every nested
      // fetch beneath them).
      outreachWithExpiry = await Promise.all(
        page.items.map(async (item): Promise<OutreachWithApprovalExpiry> => {
          if (item.status !== "approved" || item.approvalContractId === null) {
            return { ...item, approvalExpiresAt: null };
          }
          try {
            const approval = await client.getApproval(item.approvalContractId);
            return { ...item, approvalExpiresAt: approval?.expiresAt ?? null };
          } catch (cause) {
            console.warn(
              `[command home] approval lookup failed for outreach ${item.outreachId}`,
              cause,
            );
            return { ...item, approvalExpiresAt: null };
          }
        }),
      );
    } catch (cause) {
      outError = cause;
      outreachPage = null;
      outreachWithExpiry = [];
    } finally {
      outLoading = false;
    }
  }

  async function loadRelationships(): Promise<void> {
    if (tokenMissing) {
      return;
    }
    relLoading = true;
    relError = null;
    try {
      const client = createClient(config);
      relationshipsPage = await client.listRelationships({ first: 1 });
    } catch (cause) {
      relError = cause;
    } finally {
      relLoading = false;
    }
  }

  async function loadOperations(): Promise<void> {
    if (tokenMissing) {
      return;
    }
    opsLoading = true;
    opsError = null;
    try {
      const client = createClient(config);
      operations = await client.listOperations({ limit: 10 });
    } catch (cause) {
      opsError = cause;
    } finally {
      opsLoading = false;
      opsAttempted = true;
    }
  }

  function refreshRollUp(): void {
    // Fired independently (not Promise.all'd) — each function owns its own
    // try/catch, so one section throwing can never block or hide another.
    void loadOpportunities();
    void loadApplications();
    void loadOutreach();
    void loadRelationships();
    void loadOperations();
  }

  onMount(() => {
    void testConnection();
    refreshRollUp();
  });

  // FR-CMD-2 — freshness strip over all 4 real projections (Opportunities,
  // Applications, Relationships, Outreach). Relationships is loaded ONLY
  // for this — no Relationships section renders on this page. Operations
  // is passed through only so the exclusion is structurally provable (see
  // command-home.ts), never read for its own freshness.
  const freshnessInput = $derived(
    buildFreshnessRollupInput({
      opportunities: oppPage,
      applications: applicationsPage,
      relationships: relationshipsPage,
      outreach: outreachPage,
      operations,
    }),
  );
  const overallFreshness = $derived(rollupFreshness(freshnessInput));

  // FR-CMD-3 — Needs Attention rail, exact ordering.
  const needsAttention = $derived(
    buildNeedsAttention({
      outreach: outreachWithExpiry,
      opportunities: oppPage?.items ?? [],
      operations,
    }),
  );

  // FR-CMD-4 — past-nextActionAt rule. Permanently empty against live data
  // today (nextActionAt is always null); wired here so it renders honestly
  // the day BE-6 lands and a real due date exists. Kept out of
  // `needsAttention`'s array on purpose — FR-CMD-3's ordering is defined
  // over exactly 4 categories and does not mention applications.
  const overdueApps = $derived<readonly Application[]>(
    overdueApplications(applicationsPage?.items ?? []),
  );

  // FR-CMD-5 — single centered empty state on a fresh install. Gated on
  // both sections having actually completed a load attempt with no error,
  // so this never flashes true before the real answer is known.
  const freshInstall = $derived(
    oppAttempted &&
      opsAttempted &&
      oppError === null &&
      opsError === null &&
      isCommandHomeFreshInstall(oppPage?.items ?? [], operations),
  );

  const NEEDS_ATTENTION_TONE: Record<NeedsAttentionKind, "warning" | "danger" | "accent"> = {
    "outreach-pending-approval": "warning",
    "outreach-approval-expiring": "danger",
    "opportunity-discovered": "accent",
    "operation-active": "warning",
  };
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Command</h1>
    <p class="ccc-page-header__meta">
      Session orientation, connection setup, and the cross-entity roll-up.
    </p>
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
      <Button
        variant="primary"
        onclick={() => {
          void testConnection();
          refreshRollUp();
        }}
        disabled={checking}
      >
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

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else if freshInstall}
    <!-- FR-CMD-5 — one centered empty state, not four empty panels. -->
    <EmptyState
      title="Nothing here yet"
      description="No opportunities and no operations exist yet. Create the first opportunity from an evidence reference to get started."
    >
      <Button variant="primary" onclick={() => (window.location.href = "/opportunities")}>
        Go to Opportunities
      </Button>
    </EmptyState>
  {:else}
    <Panel
      title="Freshness"
      meta="4 real projections · Operation.freshness excluded (PRD §4)"
    >
      <div class="ccc-freshness-strip">
        <div class="ccc-freshness-strip__item">
          <span class="ccc-freshness-strip__label">Overall</span>
          <FreshnessTag freshness={overallFreshness} />
        </div>
        <div class="ccc-freshness-strip__item">
          <span class="ccc-freshness-strip__label">Opportunities</span>
          <FreshnessTag freshness={oppPage?.freshness} />
        </div>
        <div class="ccc-freshness-strip__item">
          <span class="ccc-freshness-strip__label">Applications</span>
          <FreshnessTag freshness={applicationsPage?.freshness} />
        </div>
        <div class="ccc-freshness-strip__item">
          <span class="ccc-freshness-strip__label">Relationships</span>
          <FreshnessTag freshness={relationshipsPage?.freshness} />
        </div>
        <div class="ccc-freshness-strip__item">
          <span class="ccc-freshness-strip__label">Outreach</span>
          <FreshnessTag freshness={outreachPage?.freshness} />
        </div>
      </div>
      {#if relError}
        <!-- FR-CMD-1 — Relationships has no rendered section of its own on
             this page (it is loaded only for freshness, per the FR-CMD-2
             supervisor decision), so its independent failure surfaces here,
             inline, rather than silently degrading the strip's
             Relationships tag to "unavailable" with no explanation. The
             other three freshness tags above are unaffected. -->
        <div style="margin-top: 0.75rem">
          <ErrorBanner error={relError} />
        </div>
      {/if}
    </Panel>

    <Panel title="Needs Attention" meta={`${needsAttention.length} item(s)`}>
      {#if needsAttention.length === 0 && overdueApps.length === 0}
        <p class="ccc-empty">Nothing needs attention right now.</p>
      {:else}
        {#if needsAttention.length > 0}
          <ul class="ccc-needs-attention">
            {#each needsAttention as item (item.kind + item.id)}
              <li class="ccc-needs-attention__item">
                <Badge tone={NEEDS_ATTENTION_TONE[item.kind]}>{item.reason}</Badge>
                <a href={item.href}>{item.title}</a>
              </li>
            {/each}
          </ul>
        {/if}
        {#if overdueApps.length > 0}
          <!-- FR-CMD-4 — unfireable against live data today (nextActionAt is
               permanently null); this block only renders once BE-6 lands
               and a real due date exists. -->
          <p class="ccc-empty" style="margin-top: 0.75rem">Overdue next actions</p>
          <ul class="ccc-needs-attention">
            {#each overdueApps as application (application.applicationId)}
              <li class="ccc-needs-attention__item">
                <Badge tone="danger">overdue</Badge>
                <a href={`/applications/${application.applicationId}`}>{application.nextAction ?? application.applicationId}</a>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
    </Panel>

    <Panel title="Opportunities" meta={oppPage ? `${oppPage.items.length} loaded` : undefined}>
      {#if oppError}
        <ErrorBanner error={oppError} />
      {:else if oppLoading && oppPage === null}
        <p class="ccc-empty">Loading…</p>
      {:else if (oppPage?.items.length ?? 0) === 0}
        <EmptyState
          title="No opportunities yet"
          description="Create the first opportunity from an evidence reference on the Opportunities screen."
        />
      {:else}
        <Table columns={["Employer / role", "State"]} caption="Opportunities">
          {#each (oppPage?.items ?? []).slice(0, 5) as item (item.opportunityId)}
            <tr>
              <th scope="row"><a href={`/opportunities/${item.opportunityId}`}>{item.employer} — {item.title}</a></th>
              <td>{item.status}</td>
            </tr>
          {/each}
        </Table>
        <div class="ccc-actions" style="margin-top: 0.5rem">
          <a href="/opportunities">View all opportunities →</a>
        </div>
      {/if}
    </Panel>

    <Panel
      title="Applications"
      meta={applicationsPage ? `${applicationsPage.items.length} loaded` : undefined}
    >
      {#if appError}
        <ErrorBanner error={appError} />
      {:else if appLoading && applicationsPage === null}
        <p class="ccc-empty">Loading…</p>
      {:else if (applicationsPage?.items.length ?? 0) === 0}
        <EmptyState
          title="No command originates an Application yet"
          description="applications.create does not exist in Ultradex today (PRD §11.3, BE-6)."
        />
      {:else}
        <Table columns={["Application", "Stage"]} caption="Applications">
          {#each (applicationsPage?.items ?? []).slice(0, 5) as item (item.applicationId)}
            <tr>
              <th scope="row"><a href={`/applications/${item.applicationId}`}>{item.opportunityId}</a></th>
              <td>{item.status}</td>
            </tr>
          {/each}
        </Table>
        <div class="ccc-actions" style="margin-top: 0.5rem">
          <a href="/applications">View all applications →</a>
        </div>
      {/if}
    </Panel>

    <Panel title="Outreach" meta={outreachPage ? `${outreachPage.items.length} loaded` : undefined}>
      {#if outError}
        <ErrorBanner error={outError} />
      {:else if outLoading && outreachPage === null}
        <p class="ccc-empty">Loading…</p>
      {:else if (outreachPage?.items.length ?? 0) === 0}
        <EmptyState
          title="No outreach yet"
          description="0 outreach rows exist in Ultradex today. Prepare and approve a draft from the Outreach screen."
        />
      {:else}
        <Table columns={["Outreach", "State"]} caption="Outreach">
          {#each (outreachPage?.items ?? []).slice(0, 5) as item (item.outreachId)}
            <tr>
              <th scope="row"><a href={`/outreach/${item.outreachId}`}>{item.channel}</a></th>
              <td>{item.status}</td>
            </tr>
          {/each}
        </Table>
        <div class="ccc-actions" style="margin-top: 0.5rem">
          <a href="/outreach">View all outreach →</a>
        </div>
      {/if}
    </Panel>

    <Panel title="Operations" meta={`${operations.length} loaded`}>
      {#if opsError}
        <ErrorBanner error={opsError} />
      {:else if opsLoading && !opsAttempted}
        <p class="ccc-empty">Loading…</p>
      {:else if operations.length === 0}
        <EmptyState title="No operations recorded yet" description="Every governed write lands here once submitted." />
      {:else}
        <Table columns={["Command", "State"]} caption="Recent operations">
          {#each operations.slice(0, 5) as item (item.id)}
            <tr>
              <th scope="row"><a href={`/operations/${item.id}`}>{item.command}</a></th>
              <td>{item.status}</td>
            </tr>
          {/each}
        </Table>
        <div class="ccc-actions" style="margin-top: 0.5rem">
          <a href="/operations">View all activity →</a>
        </div>
      {/if}
    </Panel>
  {/if}
</div>

<style>
  .ccc-freshness-strip {
    display: flex;
    flex-wrap: wrap;
    gap: var(--rh-space-16);
  }

  .ccc-freshness-strip__item {
    align-items: center;
    display: flex;
    gap: var(--rh-space-8);
  }

  .ccc-freshness-strip__label {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }

  .ccc-needs-attention {
    display: grid;
    gap: var(--rh-space-8);
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .ccc-needs-attention__item {
    align-items: center;
    display: flex;
    gap: var(--rh-space-8);
  }
</style>
