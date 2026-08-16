// See opportunities/[id]/+page.ts for the rationale: no id enumeration at
// build time, so this route opts out of prerendering and is served through
// adapter-static's SPA fallback (svelte.config.js, fallback: "index.html").
export const prerender = false;
