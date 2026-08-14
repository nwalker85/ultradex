import {
  UltradexTransportTimeout,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "@ultradex/sdk";

/** Browser fetch transport for the CCC glass (no Obsidian requestUrl). */
export class BrowserFetchTransport implements UltradexTransport {
  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    const controller = new AbortController();
    const timeoutError = new UltradexTransportTimeout(request.timeoutMs, false);
    const timer = setTimeout(() => {
      controller.abort(timeoutError);
    }, request.timeoutMs);

    try {
      const response = await fetch(request.url, {
        method: request.method,
        headers: request.headers,
        body: request.body,
        signal: controller.signal,
      });
      const text = await response.text();
      const headers: Record<string, string> = {};
      response.headers.forEach((value, key) => {
        headers[key] = value;
      });
      return {
        status: response.status,
        headers,
        body: text,
      };
    } catch (error) {
      if (error === timeoutError || controller.signal.aborted) {
        throw timeoutError;
      }
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
}
