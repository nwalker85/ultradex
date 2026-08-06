import {
  JOB_SEARCH_COMMAND_NAMES,
  contractHandleResponseSchema,
  jobSearchCommandSchema,
  type ContractHandle,
  type JobSearchCommand,
} from "./contracts.js";
import {
  UltradexAuthError,
  UltradexError,
  UltradexHttpError,
  UltradexSchemaError,
  UltradexTimeoutError,
  UltradexTransportError,
  UltradexTransportTimeout,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "./transport.js";

export { JOB_SEARCH_COMMAND_NAMES };

export interface JobSearchCommandOptions {
  readonly idempotencyKey: string;
  readonly delegationId?: string;
  readonly correlationId?: string;
}

export interface JobSearchCommandExecutorOptions {
  readonly baseUrl: string;
  readonly token: string;
  readonly transport: UltradexTransport;
  readonly timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 10_000;

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

function validateIdempotencyKey(idempotencyKey: string): string {
  if (idempotencyKey.trim().length === 0) {
    throw new TypeError("idempotencyKey must be non-empty");
  }
  return idempotencyKey;
}

function commandParameters(
  command: JobSearchCommand,
): Readonly<Record<string, string>> {
  switch (command.commandName) {
    case "sources.ingest":
      return {
        source_kind: command.parameters.sourceKind,
        source_ref: command.parameters.sourceRef,
        observed_at: command.parameters.observedAt,
      };
    case "opportunities.create":
      return {
        employer: command.parameters.employer,
        title: command.parameters.title,
        source_evidence_id: command.parameters.sourceEvidenceId,
      };
    case "opportunities.score":
      return {
        opportunity_id: command.parameters.opportunityId,
        lens: command.parameters.lens,
      };
    case "applications.transition":
      return {
        application_id: command.parameters.applicationId,
        status: command.parameters.status,
        occurred_at: command.parameters.occurredAt,
      };
    case "relationships.sync":
      return {
        opportunity_id: command.parameters.opportunityId,
        dex_contact_ref: command.parameters.dexContactRef,
      };
    case "outreach.prepare":
      return {
        opportunity_id: command.parameters.opportunityId,
        channel: command.parameters.channel,
        message_commitment: command.parameters.messageCommitment,
        ...(command.parameters.relationshipId === undefined
          ? {}
          : { relationship_id: command.parameters.relationshipId }),
      };
    case "outreach.approve":
      return {
        outreach_id: command.parameters.outreachId,
        message_commitment: command.parameters.messageCommitment,
      };
    case "outreach.send":
      return {
        outreach_id: command.parameters.outreachId,
        approval_contract_id: command.parameters.approvalContractId,
        message_commitment: command.parameters.messageCommitment,
        channel: command.parameters.channel,
      };
    case "evidence.export":
      return {
        subject_type: command.parameters.subjectType,
        subject_id: command.parameters.subjectId,
        profile: command.parameters.profile,
      };
  }
}

function schemaError(value: unknown): ContractHandle {
  const parsed = contractHandleResponseSchema.safeParse(value);
  if (!parsed.success) {
    throw new UltradexSchemaError(
      "schema_mismatch",
      parsed.error.issues.map((issue) => ({
        code: issue.code,
        message: issue.message,
        path: issue.path.map((part) =>
          typeof part === "symbol" ? String(part) : part,
        ),
      })),
    );
  }
  return parsed.data;
}

export class JobSearchCommandExecutor {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly transport: UltradexTransport;
  private readonly timeoutMs: number;

  constructor(options: JobSearchCommandExecutorOptions) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.token = validateToken(options.token);
    this.transport = options.transport;
    this.timeoutMs = validateTimeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  }

  async submit(
    input: JobSearchCommand,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    const idempotencyKey = validateIdempotencyKey(options.idempotencyKey);
    const command = jobSearchCommandSchema.parse(input);
    const headers: Record<string, string> = {
      Accept: "application/json",
      Authorization: `Bearer ${this.token}`,
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      ...(options.correlationId === undefined
        ? {}
        : { "X-Correlation-Id": options.correlationId }),
      ...(options.delegationId === undefined
        ? {}
        : { "X-Delegation-Id": options.delegationId }),
    };
    const request: UltradexRequest = {
      method: "POST",
      url:
        `${this.baseUrl}/api/v2/job-search/commands/` +
        command.commandName,
      headers,
      body: JSON.stringify(commandParameters(command)),
      timeoutMs: this.timeoutMs,
    };

    let response: UltradexTransportResponse;
    try {
      response = await this.transport.request(request);
    } catch (error) {
      if (error instanceof UltradexTransportTimeout) {
        throw new UltradexTimeoutError(
          error.timeoutMs,
          error.requestMayHaveCompleted,
          { cause: error },
        );
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
      if (response.status === 202 || response.status === 503) {
        throw new UltradexSchemaError("invalid_json");
      }
      if (response.status === 401 || response.status === 403) {
        throw new UltradexAuthError(response.status, undefined);
      }
      throw new UltradexHttpError(response.status, undefined);
    }

    if (response.status === 401 || response.status === 403) {
      throw new UltradexAuthError(response.status, value);
    }
    if (response.status !== 202 && response.status !== 503) {
      throw new UltradexHttpError(response.status, value);
    }
    return schemaError(value);
  }
}
