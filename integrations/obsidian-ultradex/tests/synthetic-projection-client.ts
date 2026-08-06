import {
  UltradexClient,
  type ProjectionStatus,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "@ultradex/sdk";

import {
  syntheticApplicationPage,
  syntheticCompletedOperation,
  syntheticOpportunityPage,
  syntheticOutreachPage,
  syntheticRelationshipPage,
} from "../../../sdk/typescript/tests/fixtures.js";
import { ProjectionStore } from "../src/projection-store.js";

type QueryName =
  | "ListOpportunities"
  | "ListApplications"
  | "ListRelationships"
  | "ListOutreach"
  | "ListOperations";

export type SyntheticProjectionName =
  | "opportunities"
  | "applications"
  | "relationships"
  | "outreach";

export type SyntheticReadName =
  | SyntheticProjectionName
  | "operations";

interface SyntheticFreshnessOverride {
  readonly status: ProjectionStatus;
  readonly projectedAt?: string;
}

const VALID_QUERY_DATA: Readonly<Record<QueryName, unknown>> = {
  ListOpportunities: { opportunities: syntheticOpportunityPage },
  ListApplications: { applications: syntheticApplicationPage },
  ListRelationships: { relationships: syntheticRelationshipPage },
  ListOutreach: { outreach: syntheticOutreachPage },
  ListOperations: { operations: [syntheticCompletedOperation] },
};

function queryName(request: UltradexRequest): QueryName {
  const body = JSON.parse(request.body ?? "{}") as { readonly query?: unknown };
  const match =
    typeof body.query === "string"
      ? /query (List\w+)/u.exec(body.query)
      : null;
  if (match === null || !(match[1] in VALID_QUERY_DATA)) {
    throw new Error("Unexpected synthetic SDK request");
  }
  return match[1] as QueryName;
}

export class SyntheticProjectionTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];
  readonly freshnessOverrides: Partial<
    Record<SyntheticProjectionName, SyntheticFreshnessOverride>
  > = {};
  outreachItemsOverride: readonly unknown[] | null = null;
  emptyProjection = false;
  graphqlFailureProjection: SyntheticReadName | null = null;
  schemaFailureProjection: SyntheticReadName | null = null;
  failureMode:
    | "none"
    | "authentication"
    | "graphql"
    | "network" = "none";

  constructor(
    private readonly gate: Promise<void> = Promise.resolve(),
  ) {}

  setAllFresh(): void {
    this.freshnessOverrides.opportunities = { status: "fresh" };
    this.freshnessOverrides.applications = { status: "fresh" };
    this.freshnessOverrides.relationships = { status: "fresh" };
    this.freshnessOverrides.outreach = { status: "fresh" };
  }

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    await this.gate;
    const name = queryName(request);
    const readName: SyntheticReadName =
      name === "ListOpportunities"
        ? "opportunities"
        : name === "ListApplications"
          ? "applications"
          : name === "ListRelationships"
            ? "relationships"
            : name === "ListOutreach"
              ? "outreach"
              : "operations";
    if (this.failureMode === "network") {
      throw new TypeError("synthetic network boundary failure");
    }
    if (this.failureMode === "authentication") {
      return {
        status: 401,
        headers: { "content-type": "application/json" },
        body: '{"detail":"synthetic credential rejected"}',
      };
    }
    if (
      this.failureMode === "graphql" ||
      this.graphqlFailureProjection === readName
    ) {
      return {
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          data: null,
          errors: [
            {
              message: "Synthetic upstream detail must not reach the monitor",
              path: ["syntheticProjection"],
            },
          ],
        }),
      };
    }
    let data: unknown;
    if (this.emptyProjection) {
      data =
        name === "ListOperations"
          ? { operations: [] }
          : {
              [name === "ListOpportunities"
                ? "opportunities"
                : name === "ListApplications"
                  ? "applications"
                  : name === "ListRelationships"
                    ? "relationships"
                    : "outreach"]: {
                items: [],
                freshness: null,
                nextCursor: null,
              },
            };
    } else {
      data = VALID_QUERY_DATA[name];
      if (
        name === "ListOutreach" &&
        this.outreachItemsOverride !== null
      ) {
        data = {
          outreach: {
            ...syntheticOutreachPage,
            items: this.outreachItemsOverride,
          },
        };
      }
      if (this.schemaFailureProjection === readName) {
        data =
          readName === "operations"
            ? { operations: [{ id: "operation-invalid-schema" }] }
            : {
                [readName]: {
                  items: [],
                  freshness: null,
                },
              };
      }
      const projectionName =
        name === "ListOpportunities"
          ? "opportunities"
          : name === "ListApplications"
            ? "applications"
            : name === "ListRelationships"
              ? "relationships"
              : name === "ListOutreach"
                ? "outreach"
                : null;
      const override =
        projectionName === null
          ? undefined
          : this.freshnessOverrides[projectionName];
      if (
        projectionName !== null &&
        override !== undefined &&
        this.schemaFailureProjection !== readName
      ) {
        const page = (data as Record<string, unknown>)[
          projectionName
        ] as {
          readonly freshness: Record<string, unknown> | null;
        };
        data = {
          [projectionName]: {
            ...page,
            freshness:
              page.freshness === null
                ? null
                : {
                    ...page.freshness,
                    status: override.status,
                    ...(override.projectedAt === undefined
                      ? {}
                      : { projectedAt: override.projectedAt }),
                  },
          },
        };
      }
    }
    return {
      status: 200,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ data }),
    };
  }
}

export function createProjectionStore(
  transport: UltradexTransport,
): ProjectionStore {
  return new ProjectionStore(createProjectionClient(transport), {
    now: () => new Date("2026-07-29T15:00:00.000Z"),
  });
}

export function createProjectionClient(
  transport: UltradexTransport,
): UltradexClient {
  return new UltradexClient({
    baseUrl: "https://synthetic.invalid",
    token: "synthetic-secret-value",
    transport,
  });
}
