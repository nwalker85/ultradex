# CCC Glass — local Career Command Center Director

SvelteKit static SPA over Ultradex (Python). ML stays on the backend.

## Dev

From repo root (`ultradex` workspace):

```bash
npm install
npm run build --workspace=@ultradex/sdk
npm run dev --workspace=ccc-glass
```

Open `http://127.0.0.1:5175`. Paste `ULTRADEX_API_TOKEN` from the local runtime `.env`
(or 1P *Ultradex Local Obsidian Operator* → operator token). Base URL default
`http://127.0.0.1:8000`.

## Container

```bash
docker build -f apps/web/Dockerfile -t ccc-glass:local .
docker run --rm -p 8080:8080 ccc-glass:local
```

Point the glass UI at the host Ultradex API (`http://host.docker.internal:8000`
on Docker Desktop, or your LAN Tailscale IP).

## Stack

- `@ravenhelm/ui-svelte` — primitives
- `@ultradex/sdk` — projections + commands
- No Obsidian, no shadcn, no charts
