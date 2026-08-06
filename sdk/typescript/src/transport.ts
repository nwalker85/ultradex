import { z, type ZodType } from "zod";

export type UltradexHttpMethod = "GET" | "POST";

export interface UltradexRequest {
  readonly method: UltradexHttpMethod;
  readonly url: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly body?: string;
  readonly timeoutMs: number;
}

export interface UltradexTransportResponse {
  readonly status: number;
  readonly body: string;
  readonly headers?: Readonly<Record<string, string>>;
}

export interface UltradexTransport {
  request(request: UltradexRequest): Promise<UltradexTransportResponse>;
}

export class UltradexTransportTimeout extends Error {
  readonly name = "UltradexTransportTimeout";

  constructor(
    readonly timeoutMs: number,
    options?: { readonly cause?: unknown },
  ) {
    super(
      `Ultradex transport timed out after ${timeoutMs}ms`,
      options === undefined || options.cause === undefined
        ? undefined
        : { cause: options.cause },
    );
  }
}

export type UltradexErrorCode =
  | "transport"
  | "timeout"
  | "http"
  | "authentication"
  | "graphql"
  | "schema";

export abstract class UltradexError extends Error {
  abstract readonly code: UltradexErrorCode;
}

export class UltradexTransportError extends UltradexError {
  readonly name = "UltradexTransportError";
  readonly code = "transport" as const;

  constructor(
    message = "Ultradex transport request failed",
    options?: { readonly cause?: unknown },
  ) {
    super(
      message,
      options === undefined || options.cause === undefined
        ? undefined
        : { cause: options.cause },
    );
  }
}

export class UltradexTimeoutError extends UltradexError {
  readonly name = "UltradexTimeoutError";
  readonly code = "timeout" as const;

  constructor(
    readonly timeoutMs: number,
    options?: { readonly cause?: unknown },
  ) {
    super(
      `Ultradex request timed out after ${timeoutMs}ms`,
      options === undefined || options.cause === undefined
        ? undefined
        : { cause: options.cause },
    );
  }
}

export class UltradexHttpError extends UltradexError {
  readonly name = "UltradexHttpError";
  readonly code = "http" as const;

  constructor(
    readonly status: number,
    readonly details: unknown,
  ) {
    super(`Ultradex request failed with HTTP ${status}`);
  }
}

export class UltradexAuthError extends UltradexError {
  readonly name = "UltradexAuthError";
  readonly code = "authentication" as const;

  constructor(
    readonly status: 401 | 403,
    readonly details: unknown,
  ) {
    super(`Ultradex authentication failed with HTTP ${status}`);
  }
}

export interface UltradexGraphQLErrorDetail {
  readonly message: string;
  readonly path?: readonly (string | number)[];
  readonly extensions?: Readonly<Record<string, unknown>>;
}

export class UltradexGraphQLError extends UltradexError {
  readonly name = "UltradexGraphQLError";
  readonly code = "graphql" as const;

  constructor(readonly errors: readonly UltradexGraphQLErrorDetail[]) {
    super("Ultradex GraphQL response contained errors");
  }
}

export type UltradexSchemaErrorReason =
  | "invalid_json"
  | "schema_mismatch";

export interface UltradexSchemaIssue {
  readonly code: string;
  readonly message: string;
  readonly path: readonly (string | number)[];
}

export class UltradexSchemaError extends UltradexError {
  readonly name = "UltradexSchemaError";
  readonly code = "schema" as const;

  constructor(
    readonly reason: UltradexSchemaErrorReason,
    readonly issues: readonly UltradexSchemaIssue[] = [],
  ) {
    super(
      reason === "invalid_json"
        ? "Ultradex response was not valid JSON"
        : "Ultradex response did not match its contract",
    );
  }
}

export interface UltradexRequestExecutorOptions {
  readonly baseUrl: string;
  readonly token: string;
  readonly transport: UltradexTransport;
  readonly timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 10_000;

const graphQLErrorDetailSchema = z
  .object({
    message: z.string().min(1),
    path: z.array(z.union([z.string(), z.number()])).optional(),
    extensions: z.record(z.string(), z.unknown()).optional(),
  })
  .passthrough();

const graphQLResponseSchema = z
  .object({
    data: z.unknown().optional(),
    errors: z.array(graphQLErrorDetailSchema).optional(),
  })
  .passthrough();

function normalizeBaseUrl(baseUrl: string): string {
  const normalized = baseUrl.trim().replace(/\/+$/u, "");
  if (normalized.length === 0) {
    throw new TypeError("baseUrl must be a non-empty URL");
  }
  return normalized;
}

function validateToken(token: string): string {
  if (token.trim().length === 0) {
    throw new TypeError("token must be non-empty");
  }
  return token;
}

function validateTimeout(timeoutMs: number): number {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new TypeError("timeoutMs must be a positive finite number");
  }
  return timeoutMs;
}

function schemaIssues(error: z.ZodError): UltradexSchemaIssue[] {
  return error.issues.map((issue) => ({
    code: issue.code,
    message: issue.message,
    path: issue.path.map((part) =>
      typeof part === "symbol" ? String(part) : part,
    ),
  }));
}

export class UltradexRequestExecutor {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly transport: UltradexTransport;
  private readonly timeoutMs: number;

  constructor(options: UltradexRequestExecutorOptions) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.token = validateToken(options.token);
    this.transport = options.transport;
    this.timeoutMs = validateTimeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  }

  async requestRest<T>(path: string, schema: ZodType<T>): Promise<T> {
    const value = await this.requestJson({
      method: "GET",
      path,
    });
    return this.validateSchema(value, schema);
  }

  async requestGraphQL<T>(
    query: string,
    variables: Readonly<Record<string, unknown>>,
    schema: ZodType<T>,
  ): Promise<T> {
    const value = await this.requestJson({
      method: "POST",
      path: "/api/graphql",
      body: JSON.stringify({ query, variables }),
    });
    const envelope = graphQLResponseSchema.safeParse(value);
    if (!envelope.success) {
      throw new UltradexSchemaError(
        "schema_mismatch",
        schemaIssues(envelope.error),
      );
    }

    const errors = envelope.data.errors;
    if (errors !== undefined && errors.length > 0) {
      throw new UltradexGraphQLError(
        errors.map((error) => ({
          message: error.message,
          ...(error.path === undefined ? {} : { path: error.path }),
          ...(error.extensions === undefined
            ? {}
            : { extensions: error.extensions }),
        })),
      );
    }
    if (!("data" in envelope.data) || envelope.data.data == null) {
      throw new UltradexSchemaError("schema_mismatch", [
        {
          code: "custom",
          message: "GraphQL response must contain non-null data",
          path: ["data"],
        },
      ]);
    }

    return this.validateSchema(envelope.data.data, schema);
  }

  private async requestJson(input: {
    readonly method: UltradexHttpMethod;
    readonly path: string;
    readonly body?: string;
  }): Promise<unknown> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      Authorization: `Bearer ${this.token}`,
    };
    if (input.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const request: UltradexRequest = {
      method: input.method,
      url: `${this.baseUrl}${input.path}`,
      headers,
      timeoutMs: this.timeoutMs,
      ...(input.body === undefined ? {} : { body: input.body }),
    };

    let response: UltradexTransportResponse;
    try {
      response = await this.transport.request(request);
    } catch (error) {
      if (error instanceof UltradexTransportTimeout) {
        throw new UltradexTimeoutError(error.timeoutMs, { cause: error });
      }
      if (error instanceof UltradexError) {
        throw error;
      }
      throw new UltradexTransportError(undefined, { cause: error });
    }

    let value: unknown;
    try {
      value = JSON.parse(response.body) as unknown;
    } catch {
      if (response.status === 401 || response.status === 403) {
        throw new UltradexAuthError(response.status, undefined);
      }
      if (response.status < 200 || response.status >= 300) {
        throw new UltradexHttpError(response.status, undefined);
      }
      throw new UltradexSchemaError("invalid_json");
    }

    if (response.status === 401 || response.status === 403) {
      throw new UltradexAuthError(response.status, value);
    }
    if (response.status < 200 || response.status >= 300) {
      throw new UltradexHttpError(response.status, value);
    }
    return value;
  }

  private validateSchema<T>(value: unknown, schema: ZodType<T>): T {
    const parsed = schema.safeParse(value);
    if (!parsed.success) {
      throw new UltradexSchemaError(
        "schema_mismatch",
        schemaIssues(parsed.error),
      );
    }
    return parsed.data;
  }
}
