<script lang="ts">
  // Presentational stubs only — no auth, no org/tenant API calls this slice.
</script>

<header class="ccc-topbar">
  <div class="ccc-topbar__brand">
    <span class="ccc-topbar__mark" aria-hidden="true">CCC</span>
    <span class="ccc-topbar__title ccc-topbar__title--full">Career Command Center</span>
    <span class="ccc-topbar__title ccc-topbar__title--short">CCC</span>
  </div>

  <div class="ccc-topbar__spacer"></div>

  <button
    type="button"
    class="ccc-topbar__tenant"
    aria-label="Current tenant: Ravenhelm"
  >
    <span class="ccc-topbar__tenant-label">Ravenhelm</span>
    <svg
      class="ccc-topbar__chevron"
      viewBox="0 0 20 20"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M5.5 8 10 12.5 14.5 8" />
    </svg>
  </button>

  <button
    type="button"
    class="ccc-topbar__user"
    aria-label="Account menu for the current user"
  >
    <span aria-hidden="true">NW</span>
  </button>
</header>

<style>
  .ccc-topbar {
    align-items: center;
    background: var(--rh-surface);
    border-bottom: 1px solid var(--rh-hairline);
    display: flex;
    flex-shrink: 0;
    gap: var(--rh-space-16);
    height: 3.5rem;
    padding: 0 var(--rh-space-16);
  }

  .ccc-topbar__brand {
    align-items: center;
    display: flex;
    gap: var(--rh-space-12);
    min-width: 0;
  }

  .ccc-topbar__mark {
    align-items: center;
    background: var(--rh-accent);
    border-radius: var(--rh-radius-6);
    color: var(--rh-primitive-neutral-950);
    display: flex;
    flex-shrink: 0;
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    font-weight: var(--rh-typography-weight-semibold);
    height: 2rem;
    justify-content: center;
    letter-spacing: 0.04em;
    width: 2rem;
  }

  .ccc-topbar__title {
    color: var(--rh-ink);
    font-family: var(--rh-display);
    font-size: var(--rh-typography-size-heading-medium);
    font-weight: var(--rh-typography-weight-semibold);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Below sm the full wordmark truncates ("Career Command C…"), so swap to the
     official acronym and drop the now-redundant mark chip. */
  .ccc-topbar__title--short {
    display: none;
  }

  .ccc-topbar__spacer {
    flex: 1;
  }

  .ccc-topbar__tenant,
  .ccc-topbar__user {
    align-items: center;
    background: transparent;
    border: 1px solid var(--rh-hairline);
    color: var(--rh-muted);
    cursor: pointer;
    display: flex;
    font: inherit;
    transition:
      background var(--rh-motion-duration-fast) var(--rh-motion-easing-standard),
      color var(--rh-motion-duration-fast) var(--rh-motion-easing-standard);
  }

  .ccc-topbar__tenant {
    border-radius: var(--rh-radius);
    gap: var(--rh-space-8);
    height: 2.25rem;
    padding: 0 var(--rh-space-12);
  }

  .ccc-topbar__tenant:hover,
  .ccc-topbar__user:hover {
    background: var(--rh-surface-raised);
    color: var(--rh-ink);
  }

  .ccc-topbar__user {
    border-radius: var(--rh-radius-full);
    flex-shrink: 0;
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    font-weight: var(--rh-typography-weight-semibold);
    height: 2.25rem;
    justify-content: center;
    width: 2.25rem;
  }

  @media (max-width: 639.98px) {
    .ccc-topbar__tenant-label {
      display: none;
    }

    .ccc-topbar__tenant {
      padding: 0 var(--rh-space-8);
    }

    .ccc-topbar__title--full,
    .ccc-topbar__mark {
      display: none;
    }

    .ccc-topbar__title--short {
      display: inline;
    }
  }
</style>
