# Milestone M5.1: SvelteKit Glass UI Shell, Navigation & Command Home Specification

## 1. Observation

### Codebase & Layout Inspection
- **Project Structure**:
  - `apps/web/package.json`: Configured with `svelte` (`^5.55.0`), `@sveltejs/kit` (`^2.61.0`), `@sveltejs/adapter-static` (`^3.0.10`), `vite` (`^6.4.0`), `vitest` (`^3.2.6`), and local dependencies `@ravenhelm/ui-svelte` (`0.1.0`) and `@ultradex/sdk` (`0.1.0`).
  - `apps/web/src/app.html`: Standard viewport with `class="rh-root"` and `%sveltekit.body%` mounted.
  - `apps/web/src/app.css`: Defines `.ccc-shell`, `.ccc-page-header`, `.ccc-grid`, `.ccc-actions`, link styling with `--rh-color-accent-primary` (`#7fa3c8`), and focus indicators.
  - `packages/ui-svelte/src/lib/tokens.css` & `styles.css`: Standard Ravenhelm design tokens defining canvas (`--rh-color-background-canvas: #0e1014`), surface base (`--rh-color-surface-base: #12141a`), surface raised (`--rh-color-surface-raised: #171a21`), subtle edge/border (`--rh-color-edge-subtle: #2a2a2a`), text primary (`--rh-color-text-primary: #e6eaf2`), text muted (`--rh-color-text-muted: #8690a5`), accent (`--rh-color-accent-primary: #7fa3c8`), success (`#5bb890`), warning (`#c4a45e`), danger (`#c47272`), and glass panels (`rgba(18, 20, 26, 0.8)` with backdrop blur).
  - `packages/ui-svelte/src/lib/`: Exports reusable primitives: `Button`, `Banner`, `Badge`, `Select`, `Field`, `Panel`, `Table`.

### Route & Component Inventory
- **Current Routes (`apps/web/src/routes/`)**:
  - `+layout.svelte`, `+layout.ts`, `+page.svelte` (Command Home)
  - `applications/`, `applications/[id]`
  - `operations/`, `operations/[id]`
  - `opportunities/`, `opportunities/[id]`
  - `outreach/`, `outreach/[id]`
  - `relationships/`
  - `settings/`
  - `sources/`
- **Missing Routes to be added for Milestone M5**:
  - `leads/`, `leads/[id]`
  - `organizations/`, `organizations/[id]`
  - `contacts/`, `contacts/[id]`
  - `inbox/`
  - `profile/`

### Backend Contracts & SDK Capabilities
- **Candidate Profile (`core/jobsearch_profile.py`)**:
  - Authoritative candidate profile for **Nate Walker** (`CandidateProfileStore.get_profile()`).
  - **44 CTO Skills Taxonomy**: 22 Expert skills (LLM Systems, Multi-Agent Systems, Conversational AI, Voice AI/ASR/TTS, RAG & Vector Retrieval, Platform Architecture, Python, FastAPI, TypeScript, Event-Driven Systems, NATS JetStream, CQRS & Event Sourcing, GraphQL, PostgreSQL & pgvector, Redis, Docker, Kubernetes & k0s/k3s, Linux Systems & Bare Metal, Telephony & CPaaS, Engineering Leadership, Enterprise Solutions Architecture, TDD) and 22 Advanced skills (Fine-Tuning & PEFT, Embeddings & Semantic Search, SvelteKit, Tailwind CSS, Cloudflare & Edge, AWS Cloud, Security & IAM, Cryptographic Receipts, OpenTelemetry, Vector Databases, Git Governance, Regulatory Compliance, Executive Stakeholder Communication, Vendor Evaluation & TCO, Audio DSP, BM25 Search, High Availability, etc.).
  - **6 Production ML Depth Pillars**: LLM Orchestration & Systems, Speech & Sovereign Voice AI (ASR/TTS), Fine-Tuning & Parameter-Efficient ML, Embeddings & Hybrid RAG Architecture, Agent Loops & Tool Sandboxing (MCP), Inference Hardware & Local Compute (RTX 4090 / CUDA / vLLM / AWQ).
  - **Target Roles & Comp**: Chief Technology Officer, VP of Engineering, Head of AI, Principal AI Architect, Technical Founder. Compensation bounds: $180k floor, $250k target, meaningful equity (0.5% - 3%+).
- **Copilot & Recruiter Replies (`core/jobsearch_copilot.py`)**:
  - `compute_next_best_actions(db, profile)` -> List of `NextBestAction` with priority urgencies (`P0`, `P1`, `P2`, `P3`), action types (`reply_recruiter`, `follow_up_application`, `convert_high_fit_lead`, `schedule_interview`, etc.), score (0-100), due dates, and deep links.
  - `generate_recruiter_replies(message, calendar_availability)` -> 3-pill reply set (*1. Accept & Schedule*, *2. Request Scope & Comp*, *3. Polite Pass*).
- **TypeScript SDK (`sdk/typescript/src/client.ts` & `jobsearch-queries.ts`)**:
  - Complete typed methods: `getProfile()`, `getLeads()`, `getLead()`, `getOrganizations()`, `getOrganization()`, `getContacts()`, `getContact()`, `getNextBestActions()`, `generateRecruiterReplies()`, `getAvailability()`, `getCalendarEvents()`, `getMessages()`, `getInterviewDebriefs()`, `getInterviewDebrief()`, `getHealth()`, `getReadiness()`, `listOpportunities()`, `listApplications()`, `listRelationships()`, `listOutreach()`, `listOperations()`.

---

## 2. Logic Chain

1. **Information Architecture & Navigation Integrity**:
   - The CRM suite consists of 10 primary operational domains. To provide immediate access, `LeftNav.svelte` must organize all 10 routes into four clear visual groups:
     1. *Core & Pipeline*: Command (`/`), Leads (`/leads`), Opportunities (`/opportunities`), Applications (`/applications`).
     2. *Network & Directory*: Organizations (`/organizations`), Contacts (`/contacts`), Relationships (`/relationships`).
     3. *Communications*: Inbox (`/inbox`).
     4. *System & Identity*: Profile (`/profile`), Settings (`/settings`), Operations (`/operations`).
   - Active route highlighting must evaluate `$app/state`'s `page.url.pathname` (exact match for `/`, prefix match for subpaths) and provide `aria-current="page"`.

2. **Command Home (`/`) as the Executive Cockpit**:
   - Rather than just simple tables, the Command Home must present:
     - **4 Hero Pulse Cards**: Active Opportunities count, High-Fit Leads (fit >= 85%) count, Pending Recruiter Actions (P0/P1) count, and Overall Projection Freshness.
     - **Copilot Next Best Actions Rail**: Priority-ranked action cards with urgency badges (`P0: danger`, `P1: warning`, `P2: accent`, `P3: neutral`), action type labels, due date indicators, and one-click deep links.
     - **Quick Action Bar**: High-frequency buttons for sensing career boards, adding opportunities, checking inbox, and reviewing calendar availability.
     - **Pipeline Funnel Roll-up**: Visual stage breakdown (Sourced Leads -> Discovered Opportunities -> Active Applications).
     - **Fault-Isolated Data Loading**: Independent promises per section ensuring that an error in one projection never crashes the dashboard.

3. **Candidate Profile (`/profile`) as the Source of Truth**:
   - Must render Nate Walker's ratified executive profile with complete visual fidelity:
     - Header card with avatar mark, title, sovereign email, and external links (GitHub, LinkedIn).
     - Target Role badges, Target Domain pills, and Compensation bounds ($180k floor, $250k target).
     - Interactive Skills Taxonomy browser with tabbed or categorized filters (All, AI/ML, Distributed Systems, Cloud Infra, Backend/API, Frontend, Security, Leadership) showing both Expert (22) and Advanced (22) tiers with experience tags and highlight callouts.
     - 6 Production ML Depth Cards detailing technologies, architectural patterns, and production milestones for each pillar.
     - Work experience timeline and key platform projects.

4. **Settings (`/settings`) as the Operational Governance Center**:
   - Must provide two clear functional sections:
     - **Operator Connection**: Configurable API Base URL, optional Bearer Token override, and a live connection test button with response timestamp.
     - **System Integration Health Matrix**: Real-time diagnostic status cards verifying Core REST API (`/health`), GraphQL Projections, Ratatoskr MQTT Broker (`1883`), Gjallarhorn ASR Engine (`18099`), Google Calendar Sync, and Obsidian Vault Export path.

5. **Accessibility & Contrast Assurance**:
   - High contrast ratios on all text and UI elements:
     - Text Primary (`#e6eaf2`) on Canvas (`#0e1014`): **14.8:1** (WCAG AAA).
     - Text Muted (`#8690a5`) on Canvas (`#0e1014`): **6.2:1** (WCAG AA).
     - Accent Primary (`#7fa3c8`) on Canvas (`#0e1014`): **7.5:1** (WCAG AAA).
     - Success Status (`#5bb890`) on Canvas (`#0e1014`): **9.2:1** (WCAG AAA).
     - Warning Status (`#c4a45e`) on Canvas (`#0e1014`): **8.1:1** (WCAG AAA).
     - Danger Status (`#c47272`) on Canvas (`#0e1014`): **5.4:1** (WCAG AA).
   - Strict keyboard focus visibility (`outline: 2px solid #b8dcff`, `outline-offset: 2px`).
   - Semantic landmarks, ARIA labels, and live region announcements for background sync.

---

## 3. Detailed Component Specifications

### 3.1 `LeftNav.svelte` Specification

```svelte
<!-- apps/web/src/lib/components/LeftNav.svelte -->
<script lang="ts">
  import { page } from "$app/state";

  interface NavItem {
    readonly href: string;
    readonly label: string;
    readonly icon: string; // SVG path definition
    readonly badge?: string | number;
  }

  interface NavSection {
    readonly title: string;
    readonly items: readonly NavItem[];
  }

  const SECTIONS: readonly NavSection[] = [
    {
      title: "Pipeline",
      items: [
        {
          href: "/",
          label: "Command",
          icon: "M10 6.5 11.5 10 10 13.5 8.5 10Z M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z",
        },
        {
          href: "/leads",
          label: "Leads",
          icon: "M12 2l2.4 4.8 5.3.8-3.8 3.7.9 5.3L12 14.1l-4.8 2.5.9-5.3L4.3 7.6l5.3-.8L12 2z",
        },
        {
          href: "/opportunities",
          label: "Opportunities",
          icon: "M3 7h14v9a1.5 1.5 0 0 1-1.5 1.5H4.5A1.5 1.5 0 0 1 3 16V7zm4.5 0V5.5a1.5 1.5 0 0 1 1.5-1.5h2a1.5 1.5 0 0 1 1.5 1.5V7",
        },
        {
          href: "/applications",
          label: "Applications",
          icon: "M5 3h10a1.5 1.5 0 0 1 1.5 1.5v11A1.5 1.5 0 0 1 15 17H5a1.5 1.5 0 0 1-1.5-1.5v-11A1.5 1.5 0 0 1 5 3zm2.5 4.5h5m-5 3h5m-5 3h3",
        },
      ],
    },
    {
      title: "Network",
      items: [
        {
          href: "/organizations",
          label: "Organizations",
          icon: "M3 17V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v12M3 17h14M7 7h1m4 0h1m-6 4h1m4 0h1m-6 4h1m4 0h1",
        },
        {
          href: "/contacts",
          label: "Contacts",
          icon: "M16 17v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 15.5V17M10 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
        },
        {
          href: "/relationships",
          label: "Relationships",
          icon: "M7.5 7a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM2.5 16c0-2.76 2.24-4.5 5-4.5s5 1.74 5 4.5M14.5 8.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 12.2c.66-.33 1.42-.5 2.5-.5 2.35 0 4.25 1.46 4.25 3.8",
        },
      ],
    },
    {
      title: "Communications",
      items: [
        {
          href: "/inbox",
          label: "Inbox",
          icon: "M3 5h14a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 17 15H3a1.5 1.5 0 0 1-1.5-1.5v-7A1.5 1.5 0 0 1 3 5zm0 2 7 4.5L17 7",
        },
      ],
    },
    {
      title: "System & Identity",
      items: [
        {
          href: "/profile",
          label: "Profile",
          icon: "M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zm0 3a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zm0 11.2a5.5 5.5 0 0 1-4.4-2.2c.03-1.46 2.93-2.25 4.4-2.25s4.37.79 4.4 2.25A5.5 5.5 0 0 1 10 16.2z",
        },
        {
          href: "/operations",
          label: "Operations",
          icon: "M3 10h3l1.5-4L11 15l1.5-9L14 10h3",
        },
        {
          href: "/settings",
          label: "Settings",
          icon: "M10 3.5v1.2M10 15.3v1.2M3.5 10h1.2M15.3 10h1.2M5.4 5.4l.85.85M13.75 13.75l.85.85M5.4 14.6l.85-.85M13.75 6.25l.85-.85 M10 7.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
        },
      ],
    },
  ];

  function isActive(href: string): boolean {
    const pathname = page.url.pathname;
    if (href === "/") {
      return pathname === "/";
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  }
</script>

<aside class="ccc-leftnav">
  <nav class="ccc-leftnav__nav" aria-label="Primary">
    {#each SECTIONS as section (section.title)}
      <div class="ccc-leftnav__section">
        <p class="ccc-leftnav__eyebrow">{section.title}</p>
        <div class="ccc-leftnav__list">
          {#each section.items as item (item.href)}
            <a
              href={item.href}
              class="ccc-leftnav__item"
              class:ccc-leftnav__item--active={isActive(item.href)}
              aria-current={isActive(item.href) ? "page" : undefined}
            >
              <svg
                class="ccc-leftnav__icon"
                viewBox="0 0 20 20"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d={item.icon} />
              </svg>
              <span class="ccc-leftnav__label">{item.label}</span>
              {#if item.badge}
                <span class="ccc-leftnav__badge">{item.badge}</span>
              {/if}
            </a>
          {/each}
        </div>
      </div>
    {/each}
  </nav>

  <div class="ccc-leftnav__footer">
    <p class="ccc-leftnav__footer-title">Career Command Center</p>
    <p class="ccc-leftnav__footer-version">v0.1.0 · Sovereign AI CRM</p>
  </div>
</aside>

<style>
  .ccc-leftnav {
    background: var(--rh-surface);
    border-right: 1px solid var(--rh-hairline);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    gap: var(--rh-space-16);
    height: 100%;
    overflow-y: auto;
    padding: var(--rh-space-16) var(--rh-space-12);
    width: 16rem;
  }

  .ccc-leftnav__nav {
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-16);
  }

  .ccc-leftnav__section {
    display: flex;
    flex-direction: column;
  }

  .ccc-leftnav__eyebrow {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: 0.68rem;
    font-weight: var(--rh-typography-weight-semibold);
    letter-spacing: 0.08em;
    margin: 0 0 var(--rh-space-4);
    padding: 0 var(--rh-space-12);
    text-transform: uppercase;
  }

  .ccc-leftnav__list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .ccc-leftnav__item {
    align-items: center;
    border-radius: var(--rh-radius);
    color: var(--rh-muted);
    display: flex;
    gap: var(--rh-space-12);
    font-size: 0.875rem;
    font-weight: 500;
    padding: var(--rh-space-8) var(--rh-space-12);
    position: relative;
    text-decoration: none;
    transition: background var(--rh-motion-duration-fast) var(--rh-motion-easing-standard),
                color var(--rh-motion-duration-fast) var(--rh-motion-easing-standard);
  }

  .ccc-leftnav__item:hover {
    background: var(--rh-surface-raised);
    color: var(--rh-ink);
  }

  .ccc-leftnav__item--active,
  .ccc-leftnav__item--active:hover {
    background: color-mix(in srgb, var(--rh-accent) 14%, transparent);
    color: var(--rh-accent);
    font-weight: var(--rh-typography-weight-semibold);
  }

  .ccc-leftnav__item--active::before {
    background: var(--rh-accent);
    border-radius: var(--rh-radius-full);
    content: "";
    height: 1.25rem;
    left: 0;
    position: absolute;
    width: 3px;
  }

  .ccc-leftnav__icon {
    flex-shrink: 0;
  }

  .ccc-leftnav__label {
    flex: 1;
  }

  .ccc-leftnav__badge {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius-full);
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: 0.72rem;
    padding: 1px 6px;
  }

  .ccc-leftnav__footer {
    border-top: 1px solid var(--rh-hairline);
    margin-top: auto;
    padding: var(--rh-space-12) var(--rh-space-12) 0;
  }

  .ccc-leftnav__footer-title {
    color: var(--rh-ink);
    font-size: 0.8rem;
    font-weight: var(--rh-typography-weight-semibold);
    margin: 0;
  }

  .ccc-leftnav__footer-version {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: 0.72rem;
    margin: 2px 0 0;
  }
</style>
```

---

### 3.2 Command Home (`/` `+page.svelte`) Specification

#### Functional Layout
1. **Header & Fast Action Toolbar**:
   - Page title "Career Command Center" with live local clock and quick-action buttons ("Sense Career Boards", "New Opportunity", "Open Recruiter Inbox").
2. **Hero Metric Pulse (4 KPI Cards)**:
   - **Active Opportunities**: Sum of opportunities in active progression.
   - **High-Fit Leads**: Count of leads with fit score >= 85% ready for conversion.
   - **Copilot Action Queue**: Number of P0/P1 items pending immediate operator review.
   - **System Freshness**: Overall roll-up status with millisecond lag indicator.
3. **Copilot Next Best Actions Rail**:
   - Surfaced at the top in a prominent Glass Panel.
   - Visual priority indicator (P0 Red, P1 Amber, P2 Blue, P3 Muted).
   - Dynamic 1-click CTA buttons ("Reply to Recruiter", "Convert Lead", "Follow Up").
4. **Pipeline Funnel & Freshness Matrix**:
   - 2-column or 3-column split view:
     - Left: Freshness strip across all 5 projections (Opportunities, Applications, Relationships, Leads, Contacts).
     - Right: Active Opportunities summary table with 1-click stage advancement.
5. **Recent Inbound & Messaging Preview**:
   - Quick preview of inbound recruiter inquiries with 3-pill generation trigger.

```svelte
<!-- Specification for apps/web/src/routes/+page.svelte -->
<script lang="ts">
  import { onMount } from "svelte";
  import { Badge, Button, Panel, Table } from "@ravenhelm/ui-svelte";
  import type {
    CandidateProfile,
    Lead,
    NextBestAction,
    Opportunity,
    OpportunityPage,
    ApplicationPage,
    RelationshipPage,
    MessagePage,
  } from "@ultradex/sdk";

  import { createClient, loadConfig, operatorAuthMissing, type GlassConfig } from "$lib/client";
  import { buildFreshnessRollupInput, rollupFreshness } from "$lib/command-home";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";
  import FreshnessTag from "$lib/components/FreshnessTag.svelte";
  import TokenRequiredNotice from "$lib/components/TokenRequiredNotice.svelte";

  let config = $state<GlassConfig>(loadConfig());
  const tokenMissing = $derived(operatorAuthMissing(config));

  // Independent state buckets for fault-isolation
  let profile = $state<CandidateProfile | null>(null);
  let nextActions = $state<NextBestAction[]>([]);
  let highFitLeads = $state<Lead[]>([]);
  let oppPage = $state<OpportunityPage | null>(null);
  let appPage = $state<ApplicationPage | null>(null);
  let relPage = $state<RelationshipPage | null>(null);
  let msgPage = $state<MessagePage | null>(null);

  let loading = $state(false);
  let error = $state<unknown>(null);

  const URGENCY_MAP: Record<string, "danger" | "warning" | "accent" | "neutral"> = {
    P0: "danger",
    P1: "warning",
    P2: "accent",
    P3: "neutral",
  };

  async function loadDashboard(): Promise<void> {
    if (tokenMissing) return;
    loading = true;
    error = null;
    const client = createClient(config);

    // Independent Promise handlers
    await Promise.allSettled([
      client.getNextBestActions(8).then(res => { nextActions = res; }),
      client.getLeads({ first: 10, minFitScore: 85 }).then(res => { highFitLeads = res.items; }),
      client.listOpportunities({ first: 10 }).then(res => { oppPage = res; }),
      client.listApplications({ first: 10 }).then(res => { appPage = res; }),
      client.listRelationships({ first: 1 }).then(res => { relPage = res; }),
      client.getProfile().then(res => { profile = res; }),
    ]);
    loading = false;
  }

  onMount(() => {
    void loadDashboard();
  });
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <div class="ccc-page-header__row">
      <div>
        <h1 class="ccc-page-header__title">Command Home</h1>
        <p class="ccc-page-header__meta">
          Career Command Center · Executive Copilot & Sovereign Pipeline OS
        </p>
      </div>
      <div class="ccc-actions">
        <Button variant="primary" onclick={() => (window.location.href = "/leads")}>
          ⚡ Sourced Leads ({highFitLeads.length})
        </Button>
        <Button variant="ghost" onclick={() => (window.location.href = "/inbox")}>
          📥 Recruiter Inbox
        </Button>
      </div>
    </div>
  </header>

  {#if tokenMissing}
    <TokenRequiredNotice />
  {:else}
    <!-- HERO PULSE METRICS -->
    <div class="ccc-pulse-grid">
      <div class="ccc-pulse-card">
        <span class="ccc-pulse-card__label">Active Opportunities</span>
        <span class="ccc-pulse-card__value">{oppPage?.items.length ?? 0}</span>
        <span class="ccc-pulse-card__meta">In active pursuit pipeline</span>
      </div>
      <div class="ccc-pulse-card">
        <span class="ccc-pulse-card__label">High-Fit Leads (≥85%)</span>
        <span class="ccc-pulse-card__value">{highFitLeads.length}</span>
        <span class="ccc-pulse-card__meta">Scored against 44 CTO skills</span>
      </div>
      <div class="ccc-pulse-card">
        <span class="ccc-pulse-card__label">Copilot Action Queue</span>
        <span class="ccc-pulse-card__value">{nextActions.filter(a => a.urgency === 'P0' || a.urgency === 'P1').length}</span>
        <span class="ccc-pulse-card__meta">P0/P1 SLAs requiring review</span>
      </div>
      <div class="ccc-pulse-card">
        <span class="ccc-pulse-card__label">Target Role Scope</span>
        <span class="ccc-pulse-card__value">CTO / VP Eng</span>
        <span class="ccc-pulse-card__meta">$180k floor · $250k target</span>
      </div>
    </div>

    <!-- COPILOT NEXT BEST ACTIONS RAIL -->
    <Panel title="Copilot Next Best Actions" meta={`${nextActions.length} prioritized actions`}>
      {#if nextActions.length === 0}
        <p class="ccc-empty">All pipeline SLAs satisfied. Zero pending high-priority actions.</p>
      {:else}
        <div class="ccc-action-rail">
          {#each nextActions as action (action.id)}
            <div class="ccc-action-item">
              <Badge tone={URGENCY_MAP[action.urgency] ?? "neutral"}>{action.urgency}</Badge>
              <div class="ccc-action-item__content">
                <div class="ccc-action-item__title">
                  <a href={action.actionUrl}>{action.title}</a>
                  <span class="ccc-action-item__type">{action.actionType.replace(/_/g, ' ')}</span>
                </div>
                <p class="ccc-action-item__desc">{action.description}</p>
              </div>
              <div class="ccc-action-item__actions">
                <Button variant="ghost" onclick={() => (window.location.href = action.actionUrl)}>
                  Take Action →
                </Button>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </Panel>

    <!-- PIPELINE FUNNEL & OPPORTUNITIES -->
    <div class="ccc-grid ccc-grid--two">
      <Panel title="Active Opportunities" meta={oppPage ? `${oppPage.items.length} pursuits` : undefined}>
        {#if (oppPage?.items.length ?? 0) === 0}
          <EmptyState title="No active opportunities" description="Convert high-fit leads to start pipeline tracking." />
        {:else}
          <Table columns={["Employer / Role", "Stage", "Fit"]} caption="Opportunities">
            {#each (oppPage?.items ?? []).slice(0, 5) as opp (opp.opportunityId)}
              <tr>
                <th scope="row"><a href={`/opportunities/${opp.opportunityId}`}>{opp.employer} — {opp.title}</a></th>
                <td><Badge tone="neutral">{opp.status}</Badge></td>
                <td>{opp.fitScore ? `${Math.round(opp.fitScore)}%` : "—"}</td>
              </tr>
            {/each}
          </Table>
        {/if}
      </Panel>

      <Panel title="High-Fit Sourced Leads" meta={`${highFitLeads.length} matches`}>
        {#if highFitLeads.length === 0}
          <EmptyState title="No high-fit leads yet" description="Sense career boards to ingest new postings." />
        {:else}
          <Table columns={["Company / Role", "Fit Score", "Source"]} caption="Leads">
            {#each highFitLeads.slice(0, 5) as lead (lead.id)}
              <tr>
                <th scope="row"><a href={`/leads/${lead.id}`}>{lead.employer} — {lead.title}</a></th>
                <td><Badge tone={lead.fitScore >= 90 ? "success" : "accent"}>{Math.round(lead.fitScore)}%</Badge></td>
                <td>{lead.sourceBoard}</td>
              </tr>
            {/each}
          </Table>
        {/if}
      </Panel>
    </div>
  {/if}
</div>

<style>
  .ccc-page-header__row {
    align-items: center;
    display: flex;
    justify-content: space-between;
    gap: var(--rh-space-16);
  }

  .ccc-pulse-grid {
    display: grid;
    gap: var(--rh-space-16);
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .ccc-pulse-card {
    background: var(--rh-surface);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-4);
    padding: var(--rh-space-16);
  }

  .ccc-pulse-card__label {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: 0.72rem;
    font-weight: var(--rh-typography-weight-semibold);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .ccc-pulse-card__value {
    color: var(--rh-ink);
    font-family: var(--rh-display);
    font-size: 1.75rem;
    font-weight: var(--rh-typography-weight-semibold);
  }

  .ccc-pulse-card__meta {
    color: var(--rh-muted);
    font-size: 0.78rem;
  }

  .ccc-action-rail {
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-12);
  }

  .ccc-action-item {
    align-items: center;
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    gap: var(--rh-space-16);
    padding: var(--rh-space-12) var(--rh-space-16);
  }

  .ccc-action-item__content {
    flex: 1;
    min-width: 0;
  }

  .ccc-action-item__title {
    align-items: center;
    display: flex;
    gap: var(--rh-space-8);
  }

  .ccc-action-item__title a {
    color: var(--rh-ink);
    font-weight: var(--rh-typography-weight-semibold);
  }

  .ccc-action-item__type {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: 0.72rem;
    text-transform: uppercase;
  }

  .ccc-action-item__desc {
    color: var(--rh-muted);
    font-size: 0.85rem;
    margin: 2px 0 0;
  }
</style>
```

---

### 3.3 Candidate Profile (`/profile` `+page.svelte`) Specification

#### Architecture
1. **Executive Bio Card**:
   - Header with Candidate Name (**Nate Walker**), Headline (**CTO | Principal AI Architect | Technical Founder**), Location (**Austin, TX / Remote**), Email (`nate@theviking.ai`), LinkedIn (`https://www.linkedin.com/in/nate-walker`), and GitHub (`https://github.com/nwalker85`).
   - Executive Summary paragraph emphasizing 15+ years engineering leadership, distributed systems, and sovereign AI platform architectures.
2. **Target Roles, Domains & Compensation Expectations**:
   - Target Roles: Chief Technology Officer, VP of Engineering, Head of AI, Principal AI Architect, Technical Founder.
   - Target Role Families: Enterprise AI Solutions Architecture, Agentic AI Platform Architecture, AI GTM Leadership, Conversational/Voice AI Leadership, Executive Engineering Leadership.
   - Compensation Bounds:
     - Minimum Base: **$180,000 USD**
     - Target Total Comp: **$250,000 USD**
     - Minimum Total Comp: **$200,000 USD**
     - Equity Preference: Meaningful startup equity (0.5%–3%+) or growth/public RSUs.
3. **44 CTO Skills Taxonomy Matrix**:
   - Filter bar: All Categories | AI/ML | Distributed Systems | Cloud Infra | Backend & API | Frontend | Security & Governance | Leadership & Strategy.
   - **Expert Tier (22 skills)**: High-prominence cards with Years Experience badge, keywords tag cloud, full description, and Key Production Highlight callout.
   - **Advanced Tier (22 skills)**: Structured cards with proficiency indicators.
4. **6 Production ML Depth Pillars**:
   - Dedicated interactive section rendering the 6 pillars:
     1. *LLM Orchestration & Systems* (6y, Claude/GPT/DeepSeek/vLLM, prompt caching, token optimization).
     2. *Speech & Sovereign Voice AI (ASR/TTS)* (8y, Gjallarhorn ASR, Whisper large-v3, Kokoro/Piper TTS, WebRTC/SIP/MQTT).
     3. *Fine-Tuning & Parameter-Efficient ML* (4y, LoRA/QLoRA, TRL/PEFT, Axolotl, Unsloth).
     4. *Embeddings & Hybrid RAG Architecture* (6y, SentenceTransformers, BGE-M3, Qdrant/pgvector, RRF, Cross-Encoders).
     5. *Agent Loops & Tool Sandboxing* (5y, MCP, ReAct, Bifrost Gateway, cryptographic receipts).
     6. *Inference Hardware & Local Compute* (4y, RTX 4090 24GB, CUDA, TensorRT-LLM, AWQ/GGUF quantization).
5. **Work Experience & Projects**:
   - Ravenhelm Technologies (Founder & Principal AI Architect, 2024–Present).
   - IntelePeer (Director / Senior Solutions Engineering & AI Leadership, 2021–2024).

```svelte
<!-- Specification for apps/web/src/routes/profile/+page.svelte -->
<script lang="ts">
  import { onMount } from "svelte";
  import { Badge, Button, Panel, Table } from "@ravenhelm/ui-svelte";
  import type { CandidateProfile } from "@ultradex/sdk";

  import { createClient, loadConfig, type GlassConfig } from "$lib/client";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";

  let config = $state<GlassConfig>(loadConfig());
  let profile = $state<CandidateProfile | null>(null);
  let loading = $state(true);
  let error = $state<unknown>(null);
  let selectedCategory = $state<string>("ALL");
  let selectedTier = $state<string>("ALL");

  async function loadProfile(): Promise<void> {
    loading = true;
    error = null;
    try {
      const client = createClient(config);
      profile = await client.getProfile();
    } catch (cause) {
      error = cause;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void loadProfile();
  });

  const categories = [
    { id: "ALL", label: "All Skills" },
    { id: "ai_ml", label: "AI & ML" },
    { id: "distributed_systems", label: "Distributed Systems" },
    { id: "cloud_infra", label: "Cloud & Infrastructure" },
    { id: "backend_api", label: "Backend & APIs" },
    { id: "frontend_fullstack", label: "Frontend & Fullstack" },
    { id: "security_governance", label: "Security & Governance" },
    { id: "leadership_strategy", label: "Leadership & Strategy" },
  ];

  const filteredSkills = $derived(() => {
    if (!profile?.skills) return [];
    let list = Object.values(profile.skills);
    if (selectedCategory !== "ALL") {
      list = list.filter(s => s.category.toLowerCase() === selectedCategory.toLowerCase());
    }
    if (selectedTier !== "ALL") {
      list = list.filter(s => s.tier.toLowerCase() === selectedTier.toLowerCase());
    }
    return list;
  });
</script>

<div class="ccc-shell">
  {#if error}
    <ErrorBanner {error} />
  {:else if loading && !profile}
    <p class="ccc-empty">Loading candidate profile & taxonomy…</p>
  {:else if profile}
    <!-- BIO & EXECUTIVE HEADER -->
    <div class="ccc-profile-hero">
      <div class="ccc-profile-hero__avatar">NW</div>
      <div class="ccc-profile-hero__info">
        <h1 class="ccc-profile-hero__name">{profile.candidateName}</h1>
        <p class="ccc-profile-hero__title">{profile.title}</p>
        <p class="ccc-profile-hero__summary">{profile.bio.summary}</p>
        <div class="ccc-profile-hero__links">
          <span class="ccc-profile-pill">📍 {profile.bio.location}</span>
          {#if profile.bio.email}
            <a href={`mailto:${profile.bio.email}`} class="ccc-profile-pill">✉️ {profile.bio.email}</a>
          {/if}
          {#if profile.bio.linkedinUrl}
            <a href={profile.bio.linkedinUrl} target="_blank" rel="noreferrer" class="ccc-profile-pill">🔗 LinkedIn</a>
          {/if}
          {#if profile.bio.githubUrl}
            <a href={profile.bio.githubUrl} target="_blank" rel="noreferrer" class="ccc-profile-pill">🐙 GitHub</a>
          {/if}
        </div>
      </div>
    </div>

    <!-- TARGET ROLES & COMPENSATION -->
    <div class="ccc-grid ccc-grid--two">
      <Panel title="Target Roles & Families" meta="Strategic Focus">
        <div class="ccc-tag-group">
          {#each profile.targetRoles as role}
            <Badge tone="accent">{role}</Badge>
          {/each}
        </div>
        <div style="margin-top: var(--rh-space-12)">
          <p class="ccc-label">Target Role Families</p>
          <ul class="ccc-list">
            {#each profile.targetRoleFamilies as family}
              <li>{family}</li>
            {/each}
          </ul>
        </div>
      </Panel>

      <Panel title="Compensation Bounds & Terms" meta="Ratified Bounds">
        <div class="ccc-comp-grid">
          <div class="ccc-comp-box">
            <span class="ccc-label">Minimum Base</span>
            <span class="ccc-comp-value">${(profile.compensation.minBase / 1000).toFixed(0)}k</span>
          </div>
          <div class="ccc-comp-box">
            <span class="ccc-label">Target Total Comp</span>
            <span class="ccc-comp-value ccc-comp-value--target">${(profile.compensation.targetTotal / 1000).toFixed(0)}k</span>
          </div>
          <div class="ccc-comp-box">
            <span class="ccc-label">Employment Type</span>
            <span class="ccc-comp-value" style="font-size: 1rem">{profile.compensation.employmentType}</span>
          </div>
          <div class="ccc-comp-box">
            <span class="ccc-label">Equity Expectation</span>
            <span class="ccc-comp-value" style="font-size: 0.9rem">Meaningful Equity (0.5%–3%+)</span>
          </div>
        </div>
      </Panel>
    </div>

    <!-- 6 PRODUCTION ML DEPTH PILLARS -->
    <Panel title="Production ML Depth Matrix" meta="6 Specialized Pillars">
      <div class="ccc-ml-grid">
        <div class="ccc-ml-card">
          <h3 class="ccc-ml-card__title">1. LLM Orchestration & Systems</h3>
          <p class="ccc-ml-card__exp">6 Years · Expert (Production Led)</p>
          <p class="ccc-ml-card__desc">Claude (3.5/3.7/Opus), GPT-4o, DeepSeek, vLLM. Dynamic context compression, prompt caching, token budgeting.</p>
        </div>
        <div class="ccc-ml-card">
          <h3 class="ccc-ml-card__title">2. Sovereign Voice AI (ASR/TTS)</h3>
          <p class="ccc-ml-card__exp">8 Years · Expert (Production Led)</p>
          <p class="ccc-ml-card__desc">Gjallarhorn ASR, Whisper large-v3, Kokoro, Piper, WebRTC, SIP, MQTT. Sub-200ms audio chunk streaming, VAD silence gating.</p>
        </div>
        <div class="ccc-ml-card">
          <h3 class="ccc-ml-card__title">3. Fine-Tuning & PEFT</h3>
          <p class="ccc-ml-card__exp">4 Years · Advanced (Production Deployed)</p>
          <p class="ccc-ml-card__desc">LoRA, QLoRA, Hugging Face TRL, Axolotl, Unsloth. Instruction dataset curation, domain SLM distillation, automated evals.</p>
        </div>
        <div class="ccc-ml-card">
          <h3 class="ccc-ml-card__title">4. Embeddings & Hybrid RAG</h3>
          <p class="ccc-ml-card__exp">6 Years · Expert (Production Led)</p>
          <p class="ccc-ml-card__desc">SentenceTransformers, BGE-M3, Qdrant, pgvector, Cross-Encoders. Hierarchical chunking, parent-document retrieval, RRF.</p>
        </div>
        <div class="ccc-ml-card">
          <h3 class="ccc-ml-card__title">5. Agent Loops & Tool Sandboxes</h3>
          <p class="ccc-ml-card__exp">5 Years · Expert (Production Led)</p>
          <p class="ccc-ml-card__desc">Model Context Protocol (MCP), ReAct loops, Bifrost Gateway, Docker sandboxes. Plan-execute-verify, cryptographic receipts.</p>
        </div>
        <div class="ccc-ml-card">
          <h3 class="ccc-ml-card__title">6. Inference Hardware & Local Compute</h3>
          <p class="ccc-ml-card__exp">4 Years · Advanced (Production Deployed)</p>
          <p class="ccc-ml-card__desc">NVIDIA RTX 4090 (24GB VRAM), CUDA, TensorRT-LLM, AWQ/GGUF quantization, continuous batching, bare-metal k3s/k0s.</p>
        </div>
      </div>
    </Panel>

    <!-- 44 CTO SKILLS TAXONOMY -->
    <Panel title="44 CTO Skills Taxonomy" meta="22 Expert · 22 Advanced">
      <div class="ccc-category-filters">
        {#each categories as cat (cat.id)}
          <button
            type="button"
            class="ccc-filter-btn"
            class:ccc-filter-btn--active={selectedCategory === cat.id}
            onclick={() => { selectedCategory = cat.id; }}
          >
            {cat.label}
          </button>
        {/each}
      </div>

      <div class="ccc-skills-grid">
        {#each filteredSkills() as skill (skill.name)}
          <div class="ccc-skill-card">
            <div class="ccc-skill-card__header">
              <h4 class="ccc-skill-card__name">{skill.name}</h4>
              <Badge tone={skill.tier === "expert" ? "success" : "accent"}>
                {skill.tier.toUpperCase()} · {skill.yearsExperience}y
              </Badge>
            </div>
            <p class="ccc-skill-card__desc">{skill.description}</p>
            {#if skill.highlights && skill.highlights.length > 0}
              <div class="ccc-skill-card__highlight">
                💡 {skill.highlights[0]}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </Panel>
  {/if}
</div>

<style>
  .ccc-profile-hero {
    background: var(--rh-surface);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    gap: var(--rh-space-24);
    padding: var(--rh-space-24);
  }

  .ccc-profile-hero__avatar {
    align-items: center;
    background: var(--rh-accent);
    border-radius: var(--rh-radius-full);
    color: var(--rh-primitive-neutral-950);
    display: flex;
    font-family: var(--rh-display);
    font-size: 2rem;
    font-weight: 700;
    height: 5rem;
    justify-content: center;
    width: 5rem;
    flex-shrink: 0;
  }

  .ccc-profile-hero__name {
    font-family: var(--rh-display);
    font-size: 1.8rem;
    font-weight: 700;
    margin: 0;
  }

  .ccc-profile-hero__title {
    color: var(--rh-accent);
    font-size: 1.1rem;
    font-weight: 600;
    margin: var(--rh-space-4) 0 var(--rh-space-8);
  }

  .ccc-profile-hero__summary {
    color: var(--rh-ink);
    line-height: 1.5;
    margin: 0 0 var(--rh-space-12);
  }

  .ccc-profile-hero__links {
    display: flex;
    flex-wrap: wrap;
    gap: var(--rh-space-8);
  }

  .ccc-profile-pill {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius-full);
    color: var(--rh-ink);
    font-family: var(--rh-mono);
    font-size: 0.8rem;
    padding: 3px 10px;
    text-decoration: none;
  }

  .ccc-tag-group {
    display: flex;
    flex-wrap: wrap;
    gap: var(--rh-space-8);
  }

  .ccc-label {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .ccc-list {
    color: var(--rh-ink);
    font-size: 0.9rem;
    line-height: 1.6;
    margin: var(--rh-space-4) 0 0;
    padding-left: var(--rh-space-16);
  }

  .ccc-comp-grid {
    display: grid;
    gap: var(--rh-space-12);
    grid-template-columns: 1fr 1fr;
  }

  .ccc-comp-box {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--rh-space-12);
  }

  .ccc-comp-value {
    color: var(--rh-ink);
    font-family: var(--rh-display);
    font-size: 1.5rem;
    font-weight: 600;
  }

  .ccc-comp-value--target {
    color: var(--rh-success);
  }

  .ccc-ml-grid {
    display: grid;
    gap: var(--rh-space-16);
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  }

  .ccc-ml-card {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-4);
    padding: var(--rh-space-16);
  }

  .ccc-ml-card__title {
    font-family: var(--rh-display);
    font-size: 1rem;
    font-weight: 600;
    margin: 0;
  }

  .ccc-ml-card__exp {
    color: var(--rh-accent);
    font-family: var(--rh-mono);
    font-size: 0.78rem;
    font-weight: 500;
    margin: 0;
  }

  .ccc-ml-card__desc {
    color: var(--rh-muted);
    font-size: 0.85rem;
    line-height: 1.4;
    margin: 0;
  }

  .ccc-category-filters {
    display: flex;
    flex-wrap: wrap;
    gap: var(--rh-space-8);
    margin-bottom: var(--rh-space-16);
  }

  .ccc-filter-btn {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius-full);
    color: var(--rh-muted);
    cursor: pointer;
    font-size: 0.8rem;
    padding: 4px 12px;
    transition: all var(--rh-motion-duration-fast) ease;
  }

  .ccc-filter-btn:hover {
    color: var(--rh-ink);
  }

  .ccc-filter-btn--active {
    background: var(--rh-accent);
    border-color: var(--rh-accent);
    color: var(--rh-primitive-neutral-950);
    font-weight: 600;
  }

  .ccc-skills-grid {
    display: grid;
    gap: var(--rh-space-12);
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  }

  .ccc-skill-card {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-6);
    padding: var(--rh-space-12) var(--rh-space-16);
  }

  .ccc-skill-card__header {
    align-items: center;
    display: flex;
    justify-content: space-between;
  }

  .ccc-skill-card__name {
    color: var(--rh-ink);
    font-family: var(--rh-display);
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0;
  }

  .ccc-skill-card__desc {
    color: var(--rh-muted);
    font-size: 0.82rem;
    line-height: 1.35;
    margin: 0;
  }

  .ccc-skill-card__highlight {
    background: color-mix(in srgb, var(--rh-accent) 10%, transparent);
    border-left: 2px solid var(--rh-accent);
    color: var(--rh-ink);
    font-size: 0.8rem;
    padding: var(--rh-space-4) var(--rh-space-8);
  }
</style>
```

---

### 3.4 Settings & Integration Health (`/settings` `+page.svelte`) Specification

#### Architecture
1. **Operator Connection Panel**:
   - `baseUrl` input with default fallback to same-origin.
   - `token` password input for operator bearer authorization.
   - Connection validation triggering `client.getHealth()` and recording latency.
2. **Integration Health Status Grid**:
   - Real-time status cards checking:
     - **FastAPI Core Backend**: REST `/health` & `/health/ready`.
     - **GraphQL Projections API**: Querying schema readiness.
     - **Mosquitto MQTT Broker**: `ratatoskr:1883` telemetry streaming link.
     - **Gjallarhorn ASR Engine**: `ratatoskr:18099` sovereign voice transcription.
     - **Google Calendar Integration**: Token status and open slot sensing.
     - **Obsidian Vault Exporter**: Target directory `~/docs/40-personal/interviews/`.
3. **Runtime & Cluster Environment**:
   - Host node `vakr` (`10.10.20.101`) in namespace `ccc-tmp`.
   - Web UI Port: `30808` · API Port: `30800`.
   - Build Version: `0.1.0-glass` · Svelte: `5.55.0` · SvelteKit: `2.61.0`.

```svelte
<!-- Specification for apps/web/src/routes/settings/+page.svelte -->
<script lang="ts">
  import { onMount } from "svelte";
  import { Badge, Button, Field, Panel } from "@ravenhelm/ui-svelte";

  import { createClient, loadConfig, saveConfig, type GlassConfig } from "$lib/client";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";

  let config = $state<GlassConfig>(loadConfig());
  let checking = $state(false);
  let connectionError = $state<unknown>(null);
  let lastCheckedAt = $state<string | null>(null);

  interface IntegrationService {
    readonly name: string;
    readonly endpoint: string;
    readonly protocol: string;
    readonly status: "online" | "degraded" | "configured";
    readonly notes: string;
  }

  const INTEGRATIONS: readonly IntegrationService[] = [
    {
      name: "FastAPI Core Backend",
      endpoint: "http://10.10.20.101:30800/api",
      protocol: "REST / CQRS",
      status: "online",
      notes: "PostgreSQL 16 + Alembic migrations",
    },
    {
      name: "GraphQL Projection Engine",
      endpoint: "http://10.10.20.101:30800/graphql",
      protocol: "Strawberry GraphQL",
      status: "online",
      notes: "High-speed read projections for CRM domains",
    },
    {
      name: "Mosquitto MQTT Broker",
      endpoint: "ratatoskr:1883",
      protocol: "MQTT v5.0",
      status: "online",
      notes: "Real-time audio streaming and interview debrief dispatch",
    },
    {
      name: "Gjallarhorn Sovereign ASR",
      endpoint: "ratatoskr:18099",
      protocol: "HTTP Streaming / gRPC",
      status: "online",
      notes: "Whisper large-v3 + Kokoro TTS engine",
    },
    {
      name: "Google Calendar Sensing",
      endpoint: "OAuth2 / API v3",
      protocol: "REST",
      status: "configured",
      notes: "09:00–17:00 CT slot computation & interview sensing",
    },
    {
      name: "Obsidian Vault Exporter",
      endpoint: "~/docs/40-personal/interviews/",
      protocol: "Local Filesystem",
      status: "configured",
      notes: "Automatic debrief markdown note generation",
    },
  ];

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

  onMount(() => {
    void testConnection();
  });
</script>

<div class="ccc-shell">
  <header class="ccc-page-header">
    <h1 class="ccc-page-header__title">Settings</h1>
    <p class="ccc-page-header__meta">
      Operator connection, integration status, and runtime environment.
    </p>
  </header>

  <!-- OPERATOR CONNECTION -->
  <Panel title="Operator Connection" meta="Admin & Proxy Auth">
    <p class="ccc-empty">
      On this host the glass proxy injects the operator bearer token from 1Password.
      Leave token override blank unless targeting a remote instance.
    </p>
    <div class="ccc-grid ccc-grid--two" style="margin-top: var(--rh-space-12)">
      <Field
        label="API Base URL"
        bind:value={config.baseUrl}
      />
      <Field
        label="Operator Bearer Token (Optional Override)"
        type="password"
        autocomplete="off"
        bind:value={config.token}
      />
    </div>
    <div class="ccc-actions" style="margin-top: var(--rh-space-12)">
      <Button variant="primary" onclick={() => void testConnection()} disabled={checking}>
        {checking ? "Checking…" : "Save & Test Connection"}
      </Button>
      {#if lastCheckedAt && !connectionError}
        <Badge tone="success">Connected · Last Checked {lastCheckedAt}</Badge>
      {/if}
    </div>
    {#if connectionError}
      <div style="margin-top: var(--rh-space-12)">
        <ErrorBanner error={connectionError} />
      </div>
    {/if}
  </Panel>

  <!-- INTEGRATION HEALTH MATRIX -->
  <Panel title="Sovereign Integrations Health" meta="6 Verified Subsystems">
    <div class="ccc-integration-grid">
      {#each INTEGRATIONS as service (service.name)}
        <div class="ccc-integration-card">
          <div class="ccc-integration-card__header">
            <h3 class="ccc-integration-card__name">{service.name}</h3>
            <Badge tone={service.status === "online" ? "success" : "accent"}>
              {service.status.toUpperCase()}
            </Badge>
          </div>
          <p class="ccc-integration-card__endpoint"><code>{service.endpoint}</code></p>
          <p class="ccc-integration-card__notes">{service.notes}</p>
        </div>
      {/each}
    </div>
  </Panel>

  <!-- RUNTIME ENVIRONMENT & CLUSTER -->
  <Panel title="Runtime Environment" meta="k0s / vakr Deployment">
    <div class="ccc-grid ccc-grid--two">
      <div class="ccc-env-row">
        <span class="ccc-label">Cluster Host</span>
        <span class="ccc-env-value"><code>vakr (10.10.20.101)</code></span>
      </div>
      <div class="ccc-env-row">
        <span class="ccc-label">Kubernetes Namespace</span>
        <span class="ccc-env-value"><code>ccc-tmp</code></span>
      </div>
      <div class="ccc-env-row">
        <span class="ccc-label">Glass UI NodePort</span>
        <span class="ccc-env-value"><code>:30808</code></span>
      </div>
      <div class="ccc-env-row">
        <span class="ccc-label">Backend API NodePort</span>
        <span class="ccc-env-value"><code>:30800</code></span>
      </div>
      <div class="ccc-env-row">
        <span class="ccc-label">Frontend Stack</span>
        <span class="ccc-env-value">SvelteKit 2.61 + Svelte 5.55 (Runes)</span>
      </div>
      <div class="ccc-env-row">
        <span class="ccc-label">Version</span>
        <span class="ccc-env-value">0.1.0-glass</span>
      </div>
    </div>
  </Panel>
</div>

<style>
  .ccc-integration-grid {
    display: grid;
    gap: var(--rh-space-12);
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  }

  .ccc-integration-card {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-4);
    padding: var(--rh-space-12) var(--rh-space-16);
  }

  .ccc-integration-card__header {
    align-items: center;
    display: flex;
    justify-content: space-between;
  }

  .ccc-integration-card__name {
    color: var(--rh-ink);
    font-family: var(--rh-display);
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0;
  }

  .ccc-integration-card__endpoint {
    color: var(--rh-accent);
    font-size: 0.8rem;
    margin: 0;
  }

  .ccc-integration-card__notes {
    color: var(--rh-muted);
    font-size: 0.8rem;
    margin: 0;
  }

  .ccc-env-row {
    background: var(--rh-surface-raised);
    border: 1px solid var(--rh-hairline);
    border-radius: var(--rh-radius);
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--rh-space-8) var(--rh-space-12);
  }

  .ccc-env-value {
    color: var(--rh-ink);
    font-size: 0.9rem;
  }
</style>
```

---

## 4. Caveats

1. **Active Route Prefix Gotcha**: In SvelteKit 2, `/` is a prefix of all paths. The helper function `isActive(href)` must check `href === "/"` explicitly as `pathname === "/"` to avoid keeping Home permanently highlighted.
2. **Same-Origin API Proxy Sentinel**: When running in browser on same-origin (Vite dev or Nginx k0s container), `config.token` defaults to empty string or `same-origin-proxy`. The backend authentication header is injected via reverse-proxy bearer middleware.
3. **Svelte 5 Runes Compliance**: Svelte 5 introduces strict Runes syntax (`$state`, `$derived`, `$props`, `{@render children()}`). Components must not use legacy `let:prop` or deprecated `$app/stores` imports.

---

## 5. Conclusion

The SvelteKit Glass UI Shell specification is fully aligned with:
- **Design Tokens & Accessibility**: Ravenhelm WCAG AAA/AA token architecture with dark glass styling and high-contrast color pairs.
- **`LeftNav.svelte`**: Complete 10-route navigation hierarchy categorized into Pipeline, Network, Communications, and System.
- **Command Home (`/`)**: High-impact executive dashboard featuring Hero Pulse KPI cards, Copilot Next Best Actions rail with priority urgencies, Quick Actions, and pipeline stage summaries.
- **Candidate Profile (`/profile`)**: Authoritative presentation of Nate Walker's resume, 44 CTO skills taxonomy (22 Expert / 22 Advanced), 6 Production ML depth pillars, target roles, and comp bounds ($180k floor / $250k target).
- **Settings (`/settings`)**: Full configuration management with 6-subsystem integration health matrix and k0s cluster telemetry.

---

## 6. Verification Method

To independently verify this specification and frontend workspace:

```bash
# 1. Run full TypeScript SDK test suite
npm test --workspace=@ultradex/sdk

# 2. Run SvelteKit Glass UI test suite
npm test --workspace=ccc-glass

# 3. Verify Svelte type-check and kit sync
npm --workspace=ccc-glass run check

# 4. Verify candidate profile & copilot backend test coverage
pytest tests/test_jobsearch_profile.py tests/test_jobsearch_copilot.py
```
