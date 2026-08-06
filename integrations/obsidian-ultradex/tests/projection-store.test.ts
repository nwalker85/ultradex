import { describe, expect, test } from "vitest";

import {
  syntheticApplicationPage,
  syntheticCompletedOperation,
  syntheticOpportunityPage,
  syntheticOutreachPage,
  syntheticRelationshipPage,
} from "../../../sdk/typescript/tests/fixtures.js";
import { ProjectionStore } from "../src/projection-store.js";
import { UltradexSetupError } from "../src/settings.js";
import {
  SyntheticProjectionTransport,
  createProjectionStore,
} from "./synthetic-projection-client.js";

describe("ProjectionStore", () => {
  test("a schema failure in one projection retains the complete last valid snapshot", async () => {
    const transport = new SyntheticProjectionTransport();
    const store = createProjectionStore(transport);
    await store.refresh();
    const validSnapshot = store.getState().snapshot;

    transport.schemaFailureProjection = "relationships";
    const failedState = await store.refresh();

    expect(failedState).toMatchObject({
      status: "stale",
      errorCategory: "schema",
      failedProjection: "Relationships",
    });
    expect(failedState.snapshot).toBe(validSnapshot);
    expect(validSnapshot).toMatchObject({
      opportunities: syntheticOpportunityPage,
      applications: syntheticApplicationPage,
      relationships: syntheticRelationshipPage,
      outreach: syntheticOutreachPage,
      operations: [syntheticCompletedOperation],
      receivedAt: "2026-07-29T15:00:00.000Z",
    });
  });

  test.each([
    ["opportunities", "Opportunities"],
    ["applications", "Applications"],
    ["relationships", "Relationships"],
    ["outreach", "Outreach"],
    ["operations", "Operations"],
  ] as const)(
    "a failed %s SDK contract preserves the sanitized %s identity",
    async (projection, label) => {
      const transport = new SyntheticProjectionTransport();
      transport.setAllFresh();
      transport.schemaFailureProjection = projection;
      const store = createProjectionStore(transport);

      const state = await store.refresh();

      expect(state).toMatchObject({
        status: "unavailable",
        errorCategory: "schema",
        failedProjection: label,
        snapshot: null,
      });
    },
  );

  test("concurrent refresh calls share one complete SDK request set", async () => {
    let releaseRequests: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      releaseRequests = resolve;
    });
    const transport = new SyntheticProjectionTransport(gate);
    transport.setAllFresh();
    const store = createProjectionStore(transport);

    const firstRefresh = store.refresh();
    const secondRefresh = store.refresh();

    expect(transport.requests).toHaveLength(5);
    releaseRequests?.();
    const [firstState, secondState] = await Promise.all([
      firstRefresh,
      secondRefresh,
    ]);

    expect(transport.requests).toHaveLength(5);
    expect(secondState).toBe(firstState);
    expect(firstState).toMatchObject({
      status: "ready",
      errorCategory: null,
    });
  });

  test.each([
    {
      projection: "opportunities" as const,
      status: "stale" as const,
      label: "Opportunities",
    },
    {
      projection: "relationships" as const,
      status: "replaying" as const,
      label: "Relationships",
    },
    {
      projection: "outreach" as const,
      status: "unavailable" as const,
      label: "Outreach",
    },
  ])(
    "a schema-valid $status $projection checkpoint cannot advertise ready",
    async ({ projection, status, label }) => {
      const transport = new SyntheticProjectionTransport();
      transport.setAllFresh();
      transport.freshnessOverrides[projection] = {
        status,
        projectedAt: "2026-07-29T11:45:00+00:00",
      };
      const store = createProjectionStore(transport);

      const state = await store.refresh();

      expect(state.status).toBe("stale");
      expect(state.snapshot?.aggregateFreshness).toEqual({
        projection: label,
        status,
        projectedAt: "2026-07-29T11:45:00+00:00",
      });
    },
  );

  test("an all-fresh aggregate reports the oldest checkpoint", async () => {
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    transport.freshnessOverrides.opportunities = {
      status: "fresh",
      projectedAt: "2026-07-29T12:10:00+00:00",
    };
    transport.freshnessOverrides.applications = {
      status: "fresh",
      projectedAt: "2026-07-29T12:05:00+00:00",
    };
    transport.freshnessOverrides.relationships = {
      status: "fresh",
      projectedAt: "2026-07-29T12:01:00+00:00",
    };
    transport.freshnessOverrides.outreach = {
      status: "fresh",
      projectedAt: "2026-07-29T12:08:00+00:00",
    };
    const store = createProjectionStore(transport);

    const state = await store.refresh();

    expect(state.status).toBe("ready");
    expect(state.snapshot?.aggregateFreshness).toEqual({
      projection: "Relationships",
      status: "fresh",
      projectedAt: "2026-07-29T12:01:00+00:00",
    });
  });

  test.each([
    {
      failureMode: "authentication" as const,
      errorCategory: "authentication",
    },
    {
      failureMode: "network" as const,
      errorCategory: "offline",
    },
    {
      failureMode: "graphql" as const,
      errorCategory: "schema",
    },
  ])(
    "$errorCategory failure without a valid snapshot is unavailable rather than empty",
    async ({ failureMode, errorCategory }) => {
      const transport = new SyntheticProjectionTransport();
      transport.failureMode = failureMode;
      const store = createProjectionStore(transport);

      const failedState = await store.refresh();

      expect(failedState).toEqual({
        status: "unavailable",
        errorCategory,
        failedProjection:
          failureMode === "graphql" ? "Opportunities" : null,
        snapshot: null,
      });
    },
  );

  test.each([
    {
      failureMode: "authentication" as const,
      errorCategory: "authentication",
    },
    {
      failureMode: "network" as const,
      errorCategory: "offline",
    },
  ])(
    "a systemic $errorCategory failure retains the last valid aggregate",
    async ({ failureMode, errorCategory }) => {
      const transport = new SyntheticProjectionTransport();
      transport.setAllFresh();
      const store = createProjectionStore(transport);
      await store.refresh();
      const validSnapshot = store.getState().snapshot;
      transport.failureMode = failureMode;

      const failedState = await store.refresh();

      expect(failedState).toMatchObject({
        status: "stale",
        errorCategory,
        failedProjection: null,
      });
      expect(failedState.snapshot).toBe(validSnapshot);
    },
  );

  test("a deferred client factory reports missing SecretStorage credentials as authentication", async () => {
    const store = new ProjectionStore(() => {
      throw new UltradexSetupError("token_missing");
    });

    await expect(store.refresh()).resolves.toEqual({
      status: "unavailable",
      errorCategory: "authentication",
      failedProjection: null,
      snapshot: null,
    });
  });

  test("clearing during an in-flight refresh discards the late candidate", async () => {
    let releaseRequests: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      releaseRequests = resolve;
    });
    const transport = new SyntheticProjectionTransport(gate);
    const store = createProjectionStore(transport);

    const pendingRefresh = store.refresh();
    expect(transport.requests).toHaveLength(5);
    store.clear();
    releaseRequests?.();
    const lateState = await pendingRefresh;

    expect(lateState).toEqual({
      status: "idle",
      errorCategory: null,
      failedProjection: null,
      snapshot: null,
    });
    expect(store.getState()).toBe(lateState);
    expect(transport.requests).toHaveLength(5);
  });

  test("a failing view subscriber cannot invalidate a verified candidate", async () => {
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    const store = createProjectionStore(transport);
    store.subscribe((state) => {
      if (state.status === "ready") {
        throw new Error("synthetic view render failure");
      }
    });

    const state = await store.refresh();

    expect(state.status).toBe("ready");
    expect(state.snapshot?.opportunities.items).toHaveLength(1);
  });

  test("subscribers observe refresh states and clearing removes only the in-memory snapshot", async () => {
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    const store = createProjectionStore(transport);
    const observedStatuses: string[] = [];
    const unsubscribe = store.subscribe((state) => {
      observedStatuses.push(state.status);
    });

    await store.refresh();
    const requestsAfterRefresh = transport.requests.length;
    store.clear();
    unsubscribe();
    await store.refresh();

    expect(observedStatuses).toEqual(["loading", "ready", "idle"]);
    expect(store.getState().status).toBe("ready");
    expect(requestsAfterRefresh).toBe(5);
    expect(transport.requests).toHaveLength(10);
  });
});
