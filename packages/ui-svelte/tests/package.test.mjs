import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

test("package exports point at svelte entry, styles, and tokens", () => {
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  assert.equal(pkg.name, "@ravenhelm/ui-svelte");
  assert.ok(pkg.exports["."].svelte.includes("index.ts"));
  assert.ok(pkg.exports["./styles.css"].includes("styles.css"));
  assert.ok(pkg.exports["./tokens.css"].includes("tokens.css"));
});

test("styles import accepted RH tokens and map semantic aliases", () => {
  const css = readFileSync(join(root, "src/lib/styles.css"), "utf8");
  assert.match(css, /@import "\.\/tokens\.css"/);
  assert.match(css, /--rh-accent:\s*var\(--rh-color-accent-primary\)/);
  assert.doesNotMatch(css, /--rh-brass/);
  const tokens = readFileSync(join(root, "src/lib/tokens.css"), "utf8");
  assert.match(tokens, /--rh-color-surface-base:/);
  assert.match(tokens, /0002-scoped-figma-acceptance/);
});

test("primitive components exist", () => {
  for (const name of [
    "Button",
    "Banner",
    "Badge",
    "Select",
    "Field",
    "Panel",
    "Table",
  ]) {
    readFileSync(join(root, `src/lib/${name}.svelte`), "utf8");
  }
});
