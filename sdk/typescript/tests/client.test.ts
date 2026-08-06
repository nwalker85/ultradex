import { describe, expect, expectTypeOf, it } from "vitest";
import { z } from "zod";

import {
  UltradexAuthError,
  UltradexClient,
  UltradexGraphQLError,
  UltradexHttpError,
  UltradexSchemaError,
  UltradexTimeoutError,
  UltradexTransportTimeout,
  UltradexTransportError,
  type ContractHandle,
  type UltradexRequest,
  type UltradexReadClient,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "../src/index.js";
import {
  contractHandleResponseSchema,
  operationLifecycleEventSchema,
  operationSchema,
  projectionFreshnessSchema,
} from "../src/contracts.js";
import { UltradexRequestExecutor } from "../src/transport.js";
import {
  syntheticContractHandleResponse,
  syntheticGraphQLData,
  syntheticGraphQLErrors,
  syntheticHealthResponse,
  syntheticLifecycleEvent,
  syntheticOperation,
  syntheticProjectionFreshness,
  syntheticReadinessResponse,
  syntheticRefusedContractHandleResponse,
} from "./fixtures.js";

type QueuedResult =
  | { response: UltradexTransportResponse }
  | { error: unknown };

class RecordingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  constructor(private readonly results: QueuedResult[]) {}

  async request(request: UltradexRequest): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    const result = this.results.shift();
    if (result === undefined) {
      throw new Error("Synthetic transport queue exhausted");
    }
    if ("error" in result) {
      throw result.error;
    }
    return result.response;
  }
}

function response(status: number, body: unknown): QueuedResult {
  return {
    response: {
      status,
      body: typeof body === "string" ? body : JSON.stringify(body),
    },
  };
}

function createClient(
  transport: UltradexTransport,
  timeoutMs = 10_000,
): UltradexClient {
  return new UltradexClient({
    baseUrl: "https://ultradex.synthetic.example/",
    token: "synthetic-token",
    timeoutMs,
    transport,
  });
}

describe("UltradexClient health contracts", () => {
  it("exposes the closed typed read client without a raw query escape hatch", () => {
    const client = createClient(new RecordingTransport([]));

    expectTypeOf<UltradexClient>().toMatchTypeOf<UltradexReadClient>();
    expect(client).not.toHaveProperty("requestGraphQL");
    expect(client).not.toHaveProperty("requestRest");
  });

  it("constructs a canonical authenticated health request", async () => {
    const transport = new RecordingTransport([
      response(200, syntheticHealthResponse),
    ]);

    const health = await createClient(transport).getHealth();

    expect(health).toEqual({
      status: "ok",
      timestamp: "2026-07-29T12:00:00",
    });
    expect(transport.requests).toEqual([
      {
        method: "GET",
        url: "https://ultradex.synthetic.example/health",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
        },
        timeoutMs: 10_000,
      },
    ]);
  });

  it("constructs the canonical readiness request without duplicating slashes", async () => {
    const transport = new RecordingTransport([
      response(200, syntheticReadinessResponse),
    ]);
    const client = new UltradexClient({
      baseUrl: "https://ultradex.synthetic.example///",
      token: "synthetic-token",
      transport,
    });

    const readiness = await client.getReadiness();

    expect(readiness).toEqual({
      ready: true,
      timestamp: "2026-07-29T12:00:01",
    });
    expect(transport.requests).toEqual([
      {
        method: "GET",
        url: "https://ultradex.synthetic.example/health/ready",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
        },
        timeoutMs: 10_000,
      },
    ]);
  });
});

describe("private request executor contracts", () => {
  it("constructs the canonical authenticated GraphQL payload", async () => {
    const transport = new RecordingTransport([
      response(200, { data: syntheticGraphQLData }),
    ]);
    const executor = new UltradexRequestExecutor({
      baseUrl: "https://ultradex.synthetic.example",
      token: "synthetic-token",
      timeoutMs: 2_500,
      transport,
    });

    const data = await executor.requestGraphQL(
      "query SyntheticOperation($id: String!) { operation(id: $id) { id } }",
      { id: "operation-synthetic-001" },
      z.object({
        operation: z.object({
          id: z.string(),
        }),
      }),
    );

    expect(data).toEqual({
      operation: {
        id: "operation-synthetic-001",
      },
    });
    expect(transport.requests).toEqual([
      {
        method: "POST",
        url: "https://ultradex.synthetic.example/api/graphql",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer synthetic-token",
          "Content-Type": "application/json",
        },
        body:
          "{\"query\":\"query SyntheticOperation($id: String!) { operation(id: $id) { id } }\",\"variables\":{\"id\":\"operation-synthetic-001\"}}",
        timeoutMs: 2_500,
      },
    ]);
  });

  it("maps a rejected adapter call to a structured transport error", async () => {
    const transport = new RecordingTransport([
      { error: new Error("Synthetic adapter disconnected") },
    ]);

    const pending = createClient(transport).getHealth();

    await expect(pending).rejects.toMatchObject({
      name: "UltradexTransportError",
      code: "transport",
      message: "Ultradex transport request failed",
    });
    await expect(pending).rejects.toBeInstanceOf(UltradexTransportError);
  });

  it("maps an adapter timeout signal to the final SDK timeout error", async () => {
    const timeout = new UltradexTransportTimeout(2_500);
    const transport = new RecordingTransport([
      { error: timeout },
    ]);

    const pending = createClient(transport, 2_500).getHealth();

    await expect(pending).rejects.toMatchObject({
      name: "UltradexTimeoutError",
      code: "timeout",
      timeoutMs: 2_500,
      cause: timeout,
    });
    await expect(pending).rejects.toBeInstanceOf(UltradexTimeoutError);
  });

  it("maps authentication responses separately from other HTTP failures", async () => {
    const transport = new RecordingTransport([
      response(401, { detail: "Invalid bearer token" }),
    ]);

    const pending = createClient(transport).getHealth();

    await expect(pending).rejects.toMatchObject({
      name: "UltradexAuthError",
      code: "authentication",
      status: 401,
      details: {
        detail: "Invalid bearer token",
      },
    });
    await expect(pending).rejects.toBeInstanceOf(UltradexAuthError);
  });

  it("maps non-authentication HTTP responses with status and parsed details", async () => {
    const transport = new RecordingTransport([
      response(503, { detail: "Service not ready" }),
    ]);

    const pending = createClient(transport).getReadiness();

    await expect(pending).rejects.toMatchObject({
      name: "UltradexHttpError",
      code: "http",
      status: 503,
      details: {
        detail: "Service not ready",
      },
    });
    await expect(pending).rejects.toBeInstanceOf(UltradexHttpError);
  });

  it("maps invalid JSON to a schema error without exposing parser exceptions", async () => {
    const transport = new RecordingTransport([
      response(200, "<synthetic-invalid-json>"),
    ]);

    const pending = createClient(transport).getHealth();

    await expect(pending).rejects.toMatchObject({
      name: "UltradexSchemaError",
      code: "schema",
      reason: "invalid_json",
    });
    await expect(pending).rejects.toBeInstanceOf(UltradexSchemaError);
  });

  it("maps a valid JSON response with an invalid shape to a schema error", async () => {
    const transport = new RecordingTransport([
      response(200, { status: "green" }),
    ]);

    const pending = createClient(transport).getHealth();

    await expect(pending).rejects.toMatchObject({
      name: "UltradexSchemaError",
      code: "schema",
      reason: "schema_mismatch",
    });
  });

  it("preserves structured GraphQL errors from a successful HTTP response", async () => {
    const transport = new RecordingTransport([
      response(200, syntheticGraphQLErrors),
    ]);
    const executor = new UltradexRequestExecutor({
      baseUrl: "https://ultradex.synthetic.example",
      token: "synthetic-token",
      transport,
    });

    const pending = executor.requestGraphQL(
      "query SyntheticOperation($id: String!) { operation(id: $id) { id } }",
      { id: "operation-synthetic-001" },
      z.object({
        operation: z.object({
          id: z.string(),
        }),
      }),
    );

    await expect(pending).rejects.toMatchObject({
      name: "UltradexGraphQLError",
      code: "graphql",
      errors: [
        {
          message: "Synthetic operation is unavailable",
          path: ["operation"],
          extensions: {
            code: "SYNTHETIC_UNAVAILABLE",
          },
        },
      ],
    });
    await expect(pending).rejects.toBeInstanceOf(UltradexGraphQLError);
  });
});

describe("foundational runtime guards", () => {
  it("parses complete synthetic projection, operation, and lifecycle contracts", () => {
    expect(projectionFreshnessSchema.parse(syntheticProjectionFreshness)).toEqual(
      syntheticProjectionFreshness,
    );
    expect(operationSchema.parse(syntheticOperation)).toEqual(syntheticOperation);
    expect(
      operationLifecycleEventSchema.parse(syntheticLifecycleEvent),
    ).toEqual(syntheticLifecycleEvent);
  });

  it("maps a complete snake-case handle into the public camel-case contract", () => {
    const handle = contractHandleResponseSchema.parse(
      syntheticContractHandleResponse,
    );

    expect(handle).toEqual({
      contractId: "contract-synthetic-001",
      operationId: "operation-synthetic-001",
      status: "accepted",
      submittedAt: "2026-07-29T12:00:03+00:00",
      correlationId: "correlation-synthetic-001",
      refusalCode: null,
      refusalReason: null,
      expiresAt: "2026-07-29T12:15:03+00:00",
      statusUrl: "/operations/operation-synthetic-001",
      eventsUrl: "/operations/operation-synthetic-001/events",
    });
    expectTypeOf(handle).toEqualTypeOf<ContractHandle>();
  });

  it("infers required refusal evidence from the transformed handle schema", () => {
    const handle = contractHandleResponseSchema.parse(
      syntheticRefusedContractHandleResponse,
    );

    expect(handle).toEqual({
      contractId: "contract-synthetic-refused-001",
      operationId: "operation-synthetic-refused-001",
      status: "refused",
      submittedAt: "2026-07-29T12:00:05+00:00",
      correlationId: "correlation-synthetic-refused-001",
      refusalCode: "synthetic_policy_denied",
      refusalReason: "Synthetic policy did not authorize this operation",
      expiresAt: null,
      statusUrl: "/operations/operation-synthetic-refused-001",
      eventsUrl: "/operations/operation-synthetic-refused-001/events",
    });

    if (handle.status !== "refused") {
      throw new Error("Synthetic refused handle lost its discriminant");
    }
    expectTypeOf(handle.refusalCode).toEqualTypeOf<string>();
    expectTypeOf(handle.refusalReason).toEqualTypeOf<string>();
  });

  it("rejects a refused handle that omits its governed refusal evidence", () => {
    const incompleteRefusal = {
      ...syntheticContractHandleResponse,
      status: "refused",
      refusal_code: null,
      refusal_reason: null,
    };

    expect(() => contractHandleResponseSchema.parse(incompleteRefusal)).toThrow();
  });

  it("rejects missing operation and lifecycle payload fields", () => {
    const { result: _result, ...operationWithoutResult } = syntheticOperation;
    const { payload: _payload, ...eventWithoutPayload } = syntheticLifecycleEvent;

    expect(() => operationSchema.parse(operationWithoutResult)).toThrow();
    expect(() =>
      operationLifecycleEventSchema.parse(eventWithoutPayload),
    ).toThrow();
  });
});
