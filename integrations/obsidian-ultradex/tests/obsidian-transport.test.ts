import {
  UltradexTransportTimeout,
  UltradexTransportError,
  type UltradexRequest,
} from "@ultradex/sdk";
import { describe, expect, test } from "vitest";

import {
  ObsidianRequestTransport,
  type ObsidianRequestUrl,
  type ObsidianRequestUrlRequest,
} from "../src/obsidian-transport.js";
import {
  ULTRADEX_TOKEN_SECRET_ID,
  type ObsidianSecretStorage,
} from "../src/settings.js";

class MemorySecretStorage implements ObsidianSecretStorage {
  constructor(private readonly token: string | null) {}

  getSecret(id: string): string | null {
    return id === ULTRADEX_TOKEN_SECRET_ID ? this.token : null;
  }

  setSecret(): void {
    throw new Error("not used by transport tests");
  }
}

const SDK_REQUEST: UltradexRequest = {
  method: "POST",
  url: "https://synthetic.invalid/api/graphql",
  headers: {
    Accept: "application/json",
    Authorization: "Bearer stale-in-memory-token",
    "Content-Type": "application/json",
  },
  body: '{"query":"query Synthetic { value }"}',
  timeoutMs: 250,
};

describe("ObsidianRequestTransport", () => {
  test("maps the SDK request and response through requestUrl with the stored token", async () => {
    let receivedRequest: ObsidianRequestUrlRequest | undefined;
    let receivedSignal: AbortSignal | undefined;
    const requestUrl: ObsidianRequestUrl = async (request, signal) => {
      receivedRequest = request;
      receivedSignal = signal;
      return {
        status: 202,
        headers: { "content-type": "application/json" },
        text: '{"status":"accepted"}',
      };
    };
    const transport = new ObsidianRequestTransport({
      requestUrl,
      secretId: ULTRADEX_TOKEN_SECRET_ID,
      secretStorage: new MemorySecretStorage("synthetic-secret-value"),
    });

    const response = await transport.request(SDK_REQUEST);

    expect(receivedRequest).toEqual({
      url: "https://synthetic.invalid/api/graphql",
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: "Bearer synthetic-secret-value",
        "Content-Type": "application/json",
      },
      body: '{"query":"query Synthetic { value }"}',
      throw: false,
    });
    expect(receivedSignal?.aborted).toBe(false);
    expect(response).toEqual({
      status: 202,
      headers: { "content-type": "application/json" },
      body: '{"status":"accepted"}',
    });
  });

  test.each([
    {
      label: "SecretStorage is unavailable",
      secretStorage: undefined,
      reason: "secret_storage_unavailable",
    },
    {
      label: "the referenced token is missing",
      secretStorage: new MemorySecretStorage(null),
      reason: "token_missing",
    },
  ])("refuses before requestUrl when $label", async (example) => {
    let requestCount = 0;
    const requestUrl: ObsidianRequestUrl = async () => {
      requestCount += 1;
      return { status: 200, headers: {}, text: "{}" };
    };
    const transport = new ObsidianRequestTransport({
      requestUrl,
      secretId: ULTRADEX_TOKEN_SECRET_ID,
      secretStorage: example.secretStorage,
    });

    await expect(transport.request(SDK_REQUEST)).rejects.toMatchObject({
      name: "UltradexSetupError",
      code: "transport",
      setupCode: "authentication_setup",
      reason: example.reason,
    });
    expect(requestCount).toBe(0);
  });

  test("aborts its timeout signal and reports the SDK timeout contract", async () => {
    let receivedSignal: AbortSignal | undefined;
    const requestUrl: ObsidianRequestUrl = (_request, signal) => {
      receivedSignal = signal;
      return new Promise((_resolve, reject) => {
        signal.addEventListener(
          "abort",
          () => {
            reject(signal.reason);
          },
          { once: true },
        );
      });
    };
    const transport = new ObsidianRequestTransport({
      requestUrl,
      requestMayHaveCompletedOnTimeout: false,
      secretId: ULTRADEX_TOKEN_SECRET_ID,
      secretStorage: new MemorySecretStorage("synthetic-secret-value"),
    });

    const request = { ...SDK_REQUEST, timeoutMs: 5 };

    await expect(transport.request(request)).rejects.toMatchObject({
      name: "UltradexTransportTimeout",
      timeoutMs: 5,
      requestMayHaveCompleted: false,
    });
    expect(receivedSignal?.aborted).toBe(true);
  });

  test("marks a non-cancellable timeout ambiguous and absorbs its late rejection", async () => {
    let rejectNativeRequest:
      | ((reason: unknown) => void)
      | undefined;
    let requestCount = 0;
    const unhandledRejections: unknown[] = [];
    const recordUnhandledRejection = (reason: unknown): void => {
      unhandledRejections.push(reason);
    };
    process.on("unhandledRejection", recordUnhandledRejection);

    try {
      const requestUrl: ObsidianRequestUrl = async () => {
        requestCount += 1;
        return new Promise((_resolve, reject) => {
          rejectNativeRequest = reject;
        });
      };
      const transport = new ObsidianRequestTransport({
        requestUrl,
        secretId: ULTRADEX_TOKEN_SECRET_ID,
        secretStorage: new MemorySecretStorage("synthetic-secret-value"),
      });

      const pending = transport.request({
        ...SDK_REQUEST,
        timeoutMs: 5,
      });

      await expect(pending).rejects.toMatchObject({
        name: "UltradexTransportTimeout",
        timeoutMs: 5,
        requestMayHaveCompleted: true,
      });
      expect(requestCount).toBe(1);

      rejectNativeRequest?.(new Error("synthetic late native rejection"));
      await new Promise((resolve) => {
        setTimeout(resolve, 0);
      });

      expect(unhandledRejections).toEqual([]);
      expect(requestCount).toBe(1);
    } finally {
      process.off("unhandledRejection", recordUnhandledRejection);
    }
  });

  test("maps requestUrl failures to the SDK transport error", async () => {
    const requestUrl: ObsidianRequestUrl = async () => {
      throw new TypeError("synthetic network failure");
    };
    const transport = new ObsidianRequestTransport({
      requestUrl,
      secretId: ULTRADEX_TOKEN_SECRET_ID,
      secretStorage: new MemorySecretStorage("synthetic-secret-value"),
    });

    await expect(transport.request(SDK_REQUEST)).rejects.toBeInstanceOf(
      UltradexTransportError,
    );
  });
});
