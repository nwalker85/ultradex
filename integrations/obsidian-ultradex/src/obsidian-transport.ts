import {
  UltradexTransportError,
  UltradexTransportTimeout,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "@ultradex/sdk";
import {
  requestUrl as obsidianRequestUrl,
  type RequestUrlParam,
  type RequestUrlResponse,
} from "obsidian";

import {
  UltradexSetupError,
  type ObsidianSecretStorage,
} from "./settings.js";

export type ObsidianRequestUrlRequest = RequestUrlParam;
export type ObsidianRequestUrlResponse = Pick<
  RequestUrlResponse,
  "status" | "headers" | "text"
>;

export type ObsidianRequestUrl = (
  request: ObsidianRequestUrlRequest,
  signal: AbortSignal,
) => Promise<ObsidianRequestUrlResponse>;

export interface ObsidianRequestTransportOptions {
  readonly secretStorage: ObsidianSecretStorage | undefined;
  readonly secretId: string;
  readonly requestUrl?: ObsidianRequestUrl;
  readonly requestMayHaveCompletedOnTimeout?: boolean;
}

const defaultRequestUrl: ObsidianRequestUrl = async (request) => {
  const response = await obsidianRequestUrl(request);
  return {
    status: response.status,
    headers: response.headers,
    text: response.text,
  };
};

export class ObsidianRequestTransport implements UltradexTransport {
  private readonly requestUrl: ObsidianRequestUrl;
  private readonly requestMayHaveCompletedOnTimeout: boolean;
  private readonly secretStorage: ObsidianSecretStorage | undefined;
  private readonly secretId: string;

  constructor(options: ObsidianRequestTransportOptions) {
    this.requestUrl = options.requestUrl ?? defaultRequestUrl;
    this.requestMayHaveCompletedOnTimeout =
      options.requestMayHaveCompletedOnTimeout ?? true;
    this.secretStorage = options.secretStorage;
    this.secretId = options.secretId;
  }

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    const token = this.requireToken();
    const controller = new AbortController();
    const timeoutError = new UltradexTransportTimeout(
      request.timeoutMs,
      this.requestMayHaveCompletedOnTimeout,
    );
    let timeoutHandle: ReturnType<typeof setTimeout> | undefined;

    const timeout = new Promise<never>((_resolve, reject) => {
      timeoutHandle = setTimeout(() => {
        controller.abort(timeoutError);
        reject(timeoutError);
      }, request.timeoutMs);
    });

    const requestUrlInput: ObsidianRequestUrlRequest = {
      url: request.url,
      method: request.method,
      headers: {
        ...request.headers,
        Authorization: `Bearer ${token}`,
      },
      throw: false,
      ...(request.body === undefined ? {} : { body: request.body }),
    };

    try {
      const response = await Promise.race([
        this.requestUrl(requestUrlInput, controller.signal),
        timeout,
      ]);
      return {
        status: response.status,
        headers: response.headers,
        body: response.text,
      };
    } catch (error) {
      if (error instanceof UltradexTransportTimeout) {
        throw error;
      }
      if (controller.signal.aborted) {
        throw timeoutError;
      }
      if (error instanceof UltradexTransportError) {
        throw error;
      }
      throw new UltradexTransportError("Obsidian requestUrl failed", {
        cause: error,
      });
    } finally {
      if (timeoutHandle !== undefined) {
        clearTimeout(timeoutHandle);
      }
    }
  }

  private requireToken(): string {
    if (this.secretStorage === undefined) {
      throw new UltradexSetupError("secret_storage_unavailable");
    }
    const token = this.secretStorage.getSecret(this.secretId);
    if (token === null || token.trim().length === 0) {
      throw new UltradexSetupError("token_missing");
    }
    return token;
  }
}
