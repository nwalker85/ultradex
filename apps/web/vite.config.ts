import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5175,
    proxy: {
      "/api": {
        target: process.env.ULTRADEX_API_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.ULTRADEX_API_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    include: ["src/**/*.{test,spec}.{js,ts}"],
  },
});
