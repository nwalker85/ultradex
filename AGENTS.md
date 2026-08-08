# AGENTS — ultradex

Forgejo-primary: `nate/ultradex`. Never push `main`; never merge without Nate's
explicit approval of that PR.

## CCC glass

- Career Director product is **`apps/web`** (Svelte local container), not Obsidian.
- UI primitives: workspace package `@ravenhelm/ui-svelte` (canonical tree also at
  `~/src/platforms/ravenhelm/libraries/ravenhelm-ui-svelte`).
- Obsidian plugin path is **deprecated** — see `integrations/obsidian-ultradex/DEPRECATED.md`.
- ML stays on Python workers; do not add ML libraries to the glass.

## Doctrine

ADR-014 (+ amendment local Svelte glass) under
`~/docs/30-projects/career-command-center/`.
