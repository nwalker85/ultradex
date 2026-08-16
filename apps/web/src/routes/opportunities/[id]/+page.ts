// This route has a dynamic segment with no way to enumerate every id at
// build time. adapter-static is configured with `fallback: "index.html"`
// (svelte.config.js), so opting this route out of prerendering makes it
// served through that SPA fallback at runtime instead of failing the
// static build. ssr is already false at the root layout (+layout.ts) and
// applies here too.
export const prerender = false;
