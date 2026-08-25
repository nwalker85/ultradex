import { UltradexClient } from "@ultradex/sdk";

import { BrowserFetchTransport } from "./transport.js";

export type GlassConfig = {
  readonly baseUrl: string;
  readonly token: string;
};

const STORAGE_KEY = "ccc-glass.config";

/** SDK refuses an empty token; nginx/Vite overwrite Authorization on same-origin. */
export const SAME_ORIGIN_PROXY_SENTINEL = "same-origin-proxy";

function defaultBaseUrl(): string {
  // Prefer same-origin so Vite/nginx can proxy /api + /health (avoids CORS).
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://127.0.0.1:5175";
}

export function isCrossOriginApi(baseUrl: string, currentOrigin?: string): boolean {
  const origin =
    currentOrigin ??
    (typeof window !== "undefined" ? window.location?.origin : undefined);
  if (!origin) {
    return false;
  }
  try {
    return new URL(baseUrl, origin).origin !== origin;
  } catch {
    return true;
  }
}

/** Empty token is fine on same-origin — the deploy proxy injects the operator bearer. */
export function operatorAuthMissing(config: GlassConfig, currentOrigin?: string): boolean {
  if (config.token.trim() !== "") {
    return false;
  }
  return isCrossOriginApi(config.baseUrl, currentOrigin);
}

export function loadConfig(): GlassConfig {
  if (typeof localStorage === "undefined") {
    return { baseUrl: defaultBaseUrl(), token: "" };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {
        baseUrl: defaultBaseUrl(),
        token: "",
      };
    }
    const parsed = JSON.parse(raw) as Partial<GlassConfig>;
    const stored = parsed.baseUrl?.trim() || "";
    // Migrate broken direct-:8000 configs to same-origin proxy.
    const baseUrl =
      stored === "" || stored === "http://127.0.0.1:8000" || stored === "http://localhost:8000"
        ? defaultBaseUrl()
        : stored;
    return {
      baseUrl,
      token: parsed.token?.trim() || "",
    };
  } catch {
    return { baseUrl: defaultBaseUrl(), token: "" };
  }
}

export function saveConfig(config: GlassConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function createClient(config: GlassConfig): UltradexClient {
  return new UltradexClient({
    baseUrl: config.baseUrl.replace(/\/$/u, ""),
    token: config.token.trim() || SAME_ORIGIN_PROXY_SENTINEL,
    transport: new BrowserFetchTransport(),
  });
}
