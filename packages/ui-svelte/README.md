# @ravenhelm/ui-svelte

Svelte 5 primitives for Ravenhelm operator surfaces, styled from the **accepted
Runestack UI Library** token checkpoint (ADR-0002).

First consumer: Career Command Center local glass (`ultradex/apps/web`).

## Authority

- Figma: Runestack UI Library `r7f71mSmD9TBfzlxJygAqL`
- Tokens: copied from `@ravenhelm/ui` `src/tokens/tokens.css` (evidence
  `2026-08-02`, checksum `bb72e638…`). Regenerate upstream with
  `npm run generate:tokens`, then copy into `src/lib/tokens.css`.
- Not the brass stub theme.

## Principles

- No shadcn, no chart libraries, no icon packs by default
- Import `@ravenhelm/ui-svelte/styles.css` (pulls tokens + component layer)
- Default theme is dark (`:root` / `[data-theme="dark"]`)
- ML never lives in this package

## Components

`Button` · `Banner` · `Badge` (tones: neutral|accent|success|warning|danger) ·
`Select` · `Table` · `Panel` · `Field`

## Usage

```svelte
<script>
  import { Button, Panel, Banner, Badge } from '@ravenhelm/ui-svelte';
  import '@ravenhelm/ui-svelte/styles.css';
</script>

<Banner tone="info">Projections fresh</Banner>
<Badge tone="accent">active</Badge>
<Panel title="Opportunities">…</Panel>
<Button variant="primary">Refresh</Button>
```

## Publish

Forgejo npm registry (when authorized). Until then, consume via ultradex workspace
`packages/ui-svelte`.
