import {
  UltradexAuthError,
  UltradexGraphQLError,
  UltradexSchemaError,
  type ApplicationPage,
  type OpportunityPage,
  type Operation,
  type OutreachPage,
  type ProjectionFreshness,
  type ProjectionStatus,
  type RelationshipPage,
  type UltradexReadClient,
} from "@ultradex/sdk";

import { UltradexSetupError } from "./settings.js";

export type ProjectionStoreStatus =
  | "idle"
  | "loading"
  | "refreshing"
  | "ready"
  | "stale"
  | "unavailable";

export type ProjectionErrorCategory =
  | "authentication"
  | "offline"
  | "schema"
  | null;

export type ProjectionIdentity =
  | "Opportunities"
  | "Applications"
  | "Relationships"
  | "Outreach"
  | "Operations";

export interface AggregateProjectionFreshness {
  readonly projection: Exclude<ProjectionIdentity, "Operations">;
  readonly status: ProjectionStatus;
  readonly projectedAt: string | null;
}

export interface ProjectionSnapshot {
  readonly opportunities: OpportunityPage;
  readonly applications: ApplicationPage;
  readonly relationships: RelationshipPage;
  readonly outreach: OutreachPage;
  readonly operations: readonly Operation[];
  readonly aggregateFreshness: AggregateProjectionFreshness;
  readonly receivedAt: string;
}

export interface ProjectionStoreState {
  readonly status: ProjectionStoreStatus;
  readonly errorCategory: ProjectionErrorCategory;
  readonly failedProjection: ProjectionIdentity | null;
  readonly snapshot: ProjectionSnapshot | null;
}

export interface ProjectionStoreOptions {
  readonly now?: () => Date;
}

export type ProjectionClientProvider =
  | UltradexReadClient
  | (() => UltradexReadClient);

export type ProjectionStoreListener = (
  state: ProjectionStoreState,
) => void;

const INITIAL_STATE: ProjectionStoreState = {
  status: "idle",
  errorCategory: null,
  failedProjection: null,
  snapshot: null,
};

interface FailedProjectionRead {
  readonly projection: ProjectionIdentity;
  readonly reason: unknown;
}

class ProjectionRefreshError extends Error {
  constructor(readonly failures: readonly FailedProjectionRead[]) {
    super("One or more projection reads failed");
    this.name = "ProjectionRefreshError";
  }
}

function settledValue<T>(result: PromiseSettledResult<T>): T {
  if (result.status === "rejected") {
    throw new Error("Projection result was rejected after validation");
  }
  return result.value;
}

const FRESHNESS_READINESS: Readonly<Record<ProjectionStatus, number>> = {
  fresh: 0,
  stale: 1,
  replaying: 2,
  unavailable: 3,
};

function aggregateFreshness(
  entries: readonly {
    readonly projection: Exclude<ProjectionIdentity, "Operations">;
    readonly freshness: ProjectionFreshness | null;
  }[],
): AggregateProjectionFreshness {
  return entries
    .map(({ projection, freshness }) => ({
      projection,
      status: freshness?.status ?? "unavailable",
      projectedAt: freshness?.projectedAt ?? null,
    }))
    .reduce((leastReady, candidate) => {
      const readinessDifference =
        FRESHNESS_READINESS[candidate.status] -
        FRESHNESS_READINESS[leastReady.status];
      if (readinessDifference > 0) {
        return candidate;
      }
      if (readinessDifference < 0) {
        return leastReady;
      }
      const candidateTime =
        candidate.projectedAt === null
          ? Number.NEGATIVE_INFINITY
          : Date.parse(candidate.projectedAt);
      const leastReadyTime =
        leastReady.projectedAt === null
          ? Number.NEGATIVE_INFINITY
          : Date.parse(leastReady.projectedAt);
      return candidateTime < leastReadyTime ? candidate : leastReady;
    });
}

export class ProjectionStore {
  private readonly now: () => Date;
  private readonly listeners = new Set<ProjectionStoreListener>();
  private generation = 0;
  private state: ProjectionStoreState = INITIAL_STATE;
  private inFlight: Promise<ProjectionStoreState> | null = null;

  constructor(
    private readonly clientProvider: ProjectionClientProvider,
    options: ProjectionStoreOptions = {},
  ) {
    this.now = options.now ?? (() => new Date());
  }

  getState(): ProjectionStoreState {
    return this.state;
  }

  subscribe(listener: ProjectionStoreListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  clear(): void {
    this.generation += 1;
    this.inFlight = null;
    this.setState(INITIAL_STATE);
  }

  refresh(): Promise<ProjectionStoreState> {
    if (this.inFlight !== null) {
      return this.inFlight;
    }

    const previousSnapshot = this.state.snapshot;
    this.setState({
      status: previousSnapshot === null ? "loading" : "refreshing",
      errorCategory: null,
      failedProjection: null,
      snapshot: previousSnapshot,
    });

    const refresh = this.refreshCandidate(
      previousSnapshot,
      this.generation,
    );
    this.inFlight = refresh;
    void refresh.finally(() => {
      if (this.inFlight === refresh) {
        this.inFlight = null;
      }
    });
    return refresh;
  }

  private async refreshCandidate(
    previousSnapshot: ProjectionSnapshot | null,
    generation: number,
  ): Promise<ProjectionStoreState> {
    try {
      const client =
        typeof this.clientProvider === "function"
          ? this.clientProvider()
          : this.clientProvider;
      const projections = [
        "Opportunities",
        "Applications",
        "Relationships",
        "Outreach",
        "Operations",
      ] as const;
      const results = await Promise.allSettled([
        client.listOpportunities(),
        client.listApplications(),
        client.listRelationships(),
        client.listOutreach(),
        client.listOperations(),
      ]);
      const failures = results.flatMap((result, index) =>
        result.status === "rejected"
          ? [
              {
                projection: projections[index],
                reason: result.reason,
              },
            ]
          : [],
      );
      if (failures.length > 0) {
        throw new ProjectionRefreshError(failures);
      }
      const opportunities = settledValue(results[0]);
      const applications = settledValue(results[1]);
      const relationships = settledValue(results[2]);
      const outreach = settledValue(results[3]);
      const operations = settledValue(results[4]);
      const snapshot: ProjectionSnapshot = {
        opportunities,
        applications,
        relationships,
        outreach,
        operations,
        aggregateFreshness: aggregateFreshness([
          {
            projection: "Opportunities",
            freshness: opportunities.freshness,
          },
          {
            projection: "Applications",
            freshness: applications.freshness,
          },
          {
            projection: "Relationships",
            freshness: relationships.freshness,
          },
          {
            projection: "Outreach",
            freshness: outreach.freshness,
          },
        ]),
        receivedAt: this.now().toISOString(),
      };
      if (generation === this.generation) {
        this.setState({
          status:
            snapshot.aggregateFreshness.status === "fresh"
              ? "ready"
              : "stale",
          errorCategory: null,
          failedProjection: null,
          snapshot,
        });
      }
    } catch (error) {
      if (generation === this.generation) {
        const cause =
          error instanceof ProjectionRefreshError
            ? error.failures[0]?.reason
            : error;
        const errorCategory = this.errorCategory(cause);
        this.setState({
          status: previousSnapshot === null ? "unavailable" : "stale",
          errorCategory,
          failedProjection:
            errorCategory === "schema" &&
            error instanceof ProjectionRefreshError
              ? error.failures[0]?.projection ?? null
              : null,
          snapshot: previousSnapshot,
        });
      }
    }
    return this.state;
  }

  private errorCategory(error: unknown): Exclude<
    ProjectionErrorCategory,
    null
  > {
    if (
      error instanceof UltradexAuthError ||
      error instanceof UltradexSetupError
    ) {
      return "authentication";
    }
    if (
      error instanceof UltradexSchemaError ||
      error instanceof UltradexGraphQLError
    ) {
      return "schema";
    }
    return "offline";
  }

  private setState(state: ProjectionStoreState): void {
    this.state = state;
    for (const listener of this.listeners) {
      try {
        listener(state);
      } catch {
        // A host view failure must not invalidate a verified SDK snapshot.
      }
    }
  }
}
