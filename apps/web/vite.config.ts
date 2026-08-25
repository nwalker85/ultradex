import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const injectedOperatorAuth = process.env.ULTRADEX_API_TOKEN
  ? { Authorization: `Bearer ${process.env.ULTRADEX_API_TOKEN}` }
  : undefined;

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5175,
    proxy: {
      "/api": {
        target: process.env.ULTRADEX_API_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        headers: injectedOperatorAuth,
      },
      "/health": {
        target: process.env.ULTRADEX_API_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        headers: injectedOperatorAuth,
      },
    },
  },
  test: {
    include: ["src/**/*.{test,spec}.{js,ts}"],
  },
});
