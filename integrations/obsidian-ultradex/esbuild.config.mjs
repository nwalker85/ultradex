import esbuild from "esbuild";

await esbuild.build({
  entryPoints: ["src/main.ts"],
  bundle: true,
  external: ["obsidian"],
  format: "cjs",
  logLevel: "info",
  outfile: "main.js",
  platform: "browser",
  sourcemap: false,
  target: "es2022",
  treeShaking: true,
});
