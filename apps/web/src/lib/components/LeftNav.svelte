<script lang="ts">
  import { onMount } from "svelte";

  const firstHash = "#whats-next";

  function resolveHash(): string {
    if (typeof window === "undefined") return firstHash;
    return window.location.hash || firstHash;
  }

  let activeHash = $state(firstHash);

  onMount(() => {
    activeHash = resolveHash();
    const handleHashChange = () => {
      activeHash = resolveHash();
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  });
</script>

<aside class="ccc-leftnav">
  <p class="ccc-leftnav__eyebrow">Navigation</p>

  <nav class="ccc-leftnav__list" aria-label="Primary">
    <a
      href="#whats-next"
      class="ccc-leftnav__item"
      class:ccc-leftnav__item--active={activeHash === "#whats-next"}
      aria-current={activeHash === "#whats-next" ? "page" : undefined}
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
        <circle cx="10" cy="10" r="7" />
        <path d="M10 6.5 11.5 10 10 13.5 8.5 10Z" />
      </svg>
      <span>Command</span>
    </a>

    <a
      href="#opportunities"
      class="ccc-leftnav__item"
      class:ccc-leftnav__item--active={activeHash === "#opportunities"}
      aria-current={activeHash === "#opportunities" ? "page" : undefined}
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
        <rect x="3" y="7" width="14" height="9" rx="1.5" />
        <path d="M7.5 7V5.5a1.5 1.5 0 0 1 1.5-1.5h2a1.5 1.5 0 0 1 1.5 1.5V7" />
        <path d="M3 11h14" />
      </svg>
      <span>Opportunities</span>
    </a>

    <a
      href="#relationships"
      class="ccc-leftnav__item"
      class:ccc-leftnav__item--active={activeHash === "#relationships"}
      aria-current={activeHash === "#relationships" ? "page" : undefined}
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
        <circle cx="7.5" cy="7" r="2.5" />
        <path d="M2.5 16c0-2.76 2.24-4.5 5-4.5s5 1.74 5 4.5" />
        <circle cx="14.5" cy="8.5" r="2" />
        <path d="M12 12.2c.66-.33 1.42-.5 2.5-.5 2.35 0 4.25 1.46 4.25 3.8" />
      </svg>
      <span>Relationships</span>
    </a>

    <a
      href="#connection"
      class="ccc-leftnav__item"
      class:ccc-leftnav__item--active={activeHash === "#connection"}
      aria-current={activeHash === "#connection" ? "page" : undefined}
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
        <path d="M8 12 12 8" />
        <path d="M7 5.5 9.5 3a3 3 0 0 1 4.5 4l-1 1" />
        <path d="M13 14.5 10.5 17a3 3 0 0 1-4.5-4l1-1" />
      </svg>
      <span>Connection</span>
    </a>
  </nav>

  <div class="ccc-leftnav__footer">
    <p class="ccc-leftnav__footer-title">Career Command Center</p>
    <p class="ccc-leftnav__footer-version">0.1.0-glass</p>
  </div>
</aside>

<style>
  .ccc-leftnav {
    background: var(--rh-surface);
    border-right: 1px solid var(--rh-hairline);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    overflow-y: auto;
    padding: var(--rh-space-16);
    width: 16rem;
  }

  .ccc-leftnav__eyebrow {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    letter-spacing: 0.04em;
    margin: 0 0 var(--rh-space-12);
    padding: 0 var(--rh-space-8);
    text-transform: uppercase;
  }

  .ccc-leftnav__list {
    display: flex;
    flex-direction: column;
    gap: var(--rh-space-4);
  }

  .ccc-leftnav__item {
    align-items: center;
    border-radius: var(--rh-radius);
    color: var(--rh-muted);
    display: flex;
    gap: var(--rh-space-12);
    padding: var(--rh-space-8) var(--rh-space-12);
    text-decoration: none;
    transition:
      background var(--rh-motion-duration-fast) var(--rh-motion-easing-standard),
      color var(--rh-motion-duration-fast) var(--rh-motion-easing-standard);
  }

  .ccc-leftnav__item:hover {
    background: var(--rh-surface-raised);
    color: var(--rh-ink);
  }

  .ccc-leftnav__item--active,
  .ccc-leftnav__item--active:hover {
    background: color-mix(in srgb, var(--rh-accent) 12%, transparent);
    color: var(--rh-accent);
  }

  .ccc-leftnav__icon {
    flex-shrink: 0;
  }

  .ccc-leftnav__footer {
    border-top: 1px solid var(--rh-hairline);
    margin-top: auto;
    padding-top: var(--rh-space-16);
  }

  .ccc-leftnav__footer-title {
    color: var(--rh-ink);
    font-weight: var(--rh-typography-weight-semibold);
    margin: 0;
  }

  .ccc-leftnav__footer-version {
    color: var(--rh-muted);
    font-family: var(--rh-mono);
    font-size: var(--rh-typography-size-body-small);
    margin: var(--rh-space-4) 0 0;
  }

  @media (max-width: 767.98px) {
    .ccc-leftnav {
      display: none;
    }
  }
</style>
