import {
  syntheticCompletedOperation,
  syntheticExecutionReceiptEvidence,
  syntheticLifecycleEvent,
} from "../../../sdk/typescript/tests/fixtures.js";
import {
  type UltradexRequest,
  type UltradexTransportResponse,
} from "@ultradex/sdk";
import { describe, expect, test, vi } from "vitest";

import UltradexPlugin, {
  ULTRADEX_OPERATOR_VIEW_TYPE,
} from "../src/main.js";
import { COMMAND_CUSTODY_SECRET_ID } from "../src/mutations/command-custody-journal.js";
import { UltradexMonitorView } from "../src/views/monitor-view.js";
import {
  createTestApp,
  Notice,
  Plugin,
} from "./obsidian-runtime.js";
import {
  SyntheticProjectionTransport,
  createProjectionClient,
} from "./synthetic-projection-client.js";

class RestoredEvidenceTransport extends SyntheticProjectionTransport {
  override async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    const body = JSON.parse(request.body ?? "{}") as {
      readonly query?: string;
      readonly variables?: Readonly<Record<string, unknown>>;
    };
    const operationId = String(
      body.variables?.id ?? body.variables?.operationId,
    );
    if (body.query?.includes("GetOperationEvents")) {
      this.requests.push(request);
      return {
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          data: {
            events: [
              {
                ...syntheticLifecycleEvent,
                operationId,
              },
            ],
          },
        }),
      };
    }
    if (body.query?.includes("GetExecutionReceipt")) {
      this.requests.push(request);
      return {
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          data: {
            executionReceipt: {
              ...syntheticExecutionReceiptEvidence,
              operationId,
            },
          },
        }),
      };
    }
    if (body.query?.includes("GetOperation")) {
      this.requests.push(request);
      return {
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          data: {
            operation: {
              ...syntheticCompletedOperation,
              id: operationId,
            },
          },
        }),
      };
    }
    return super.request(request);
  }
}

describe("UltradexPlugin lifecycle", () => {
  test("load registers only the restorable operator view factory", async () => {
    const { app, leafStates } = createTestApp();
    const plugin = new UltradexPlugin(app as never, {
      id: "ultradex-operator",
      name: "Ultradex Operator",
      version: "0.1.0",
      minAppVersion: "1.11.4",
      description: "Synthetic test manifest",
      author: "Ravenhelm",
    });

    await plugin.onload();

    const hostPlugin = plugin as unknown as Plugin;
    expect(hostPlugin.registeredCommands.map(({ id }) => id)).toEqual([
      "open-operator-console",
      "refresh-projections",
      "retry-authentication",
      "clear-cached-snapshot",
    ]);
    expect(hostPlugin.registeredSettingTabs).toHaveLength(1);
    expect(hostPlugin.registeredViews.map(({ type }) => type)).toEqual([
      ULTRADEX_OPERATOR_VIEW_TYPE,
    ]);
    expect(leafStates).toEqual([]);

    const openCommand = hostPlugin.registeredCommands.find(
      ({ id }) => id === "open-operator-console",
    );
    await openCommand?.callback?.();

    expect(hostPlugin.registeredViews.map(({ type }) => type)).toEqual([
      ULTRADEX_OPERATOR_VIEW_TYPE,
    ]);
    expect(leafStates).toEqual([
      {
        type: ULTRADEX_OPERATOR_VIEW_TYPE,
        active: true,
      },
    ]);
  });

  test("the deferred native view owns refresh and clear-cache commands without vault persistence", async () => {
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    const client = createProjectionClient(transport);
    const { app } = createTestApp();
    class TestUltradexPlugin extends UltradexPlugin {
      clientCreations = 0;

      override createClient(): typeof client {
        this.clientCreations += 1;
        return client;
      }
    }
    const plugin = new TestUltradexPlugin(app as never, {
      id: "ultradex-operator",
      name: "Ultradex Operator",
      version: "0.1.0",
      minAppVersion: "1.11.4",
      description: "Synthetic test manifest",
      author: "Ravenhelm",
    });
    await plugin.onload();
    const hostPlugin = plugin as unknown as Plugin;

    expect(plugin.clientCreations).toBe(0);
    expect(transport.requests).toEqual([]);
    expect(hostPlugin.savedData).toEqual([]);
    expect(hostPlugin.registeredViews.map(({ type }) => type)).toEqual([
      ULTRADEX_OPERATOR_VIEW_TYPE,
    ]);

    const openCommand = hostPlugin.registeredCommands.find(
      ({ id }) => id === "open-operator-console",
    );
    await openCommand?.callback?.();
    const registeredView = hostPlugin.registeredViews[0];
    plugin.settings = {
      ...plugin.settings,
      baseUrl:
        "https://operator:main-secret@configured.invalid/private?token=query-secret",
    };
    const view = registeredView?.creator({}) as UltradexMonitorView;

    expect(view).toBeInstanceOf(UltradexMonitorView);
    expect(plugin.clientCreations).toBe(0);
    await view.onOpen();
    expect(plugin.clientCreations).toBe(1);
    expect(transport.requests).toHaveLength(5);
    expect(view.contentEl.textContent).toContain("Synthetic Systems");
    expect(view.contentEl.textContent).toContain("Governed commands");
    expect(view.contentEl.textContent).toContain("Send outreach");
    expect(view.contentEl.textContent).toContain(
      "https://configured.invalid",
    );
    expect(view.contentEl.textContent).not.toContain("main-secret");
    expect(view.contentEl.textContent).not.toContain("query-secret");
    expect(hostPlugin.savedData).toEqual([]);

    const clearCommand = hostPlugin.registeredCommands.find(
      ({ id }) => id === "clear-cached-snapshot",
    );
    await clearCommand?.callback?.();
    expect(transport.requests).toHaveLength(5);
    expect(hostPlugin.savedData).toEqual([]);
    expect(view.contentEl.textContent).toContain(
      "Projection data is unavailable",
    );

    const refreshCommand = hostPlugin.registeredCommands.find(
      ({ id }) => id === "refresh-projections",
    );
    await refreshCommand?.callback?.();
    expect(plugin.clientCreations).toBe(2);
    expect(transport.requests).toHaveLength(10);
    expect(view.contentEl.textContent).toContain("Connected");
  });

  test("refresh command distinguishes an installed degraded candidate from a retained failure", async () => {
    Notice.messages.length = 0;
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    const client = createProjectionClient(transport);
    const { app } = createTestApp();
    class TestUltradexPlugin extends UltradexPlugin {
      override createClient(): typeof client {
        return client;
      }
    }
    const plugin = new TestUltradexPlugin(app as never, {
      id: "ultradex-operator",
      name: "Ultradex Operator",
      version: "0.1.0",
      minAppVersion: "1.11.4",
      description: "Synthetic test manifest",
      author: "Ravenhelm",
    });
    await plugin.onload();
    const hostPlugin = plugin as unknown as Plugin;
    const registeredView = hostPlugin.registeredViews[0];
    const view = registeredView?.creator({}) as UltradexMonitorView;
    await view.onOpen();
    const refreshCommand = hostPlugin.registeredCommands.find(
      ({ id }) => id === "refresh-projections",
    );

    transport.freshnessOverrides.relationships = {
      status: "replaying",
      projectedAt: "2026-07-29T11:45:00+00:00",
    };
    await refreshCommand?.callback?.();

    expect(Notice.messages.at(-1)).toBe(
      "Ultradex projections refreshed with degraded freshness. Relationships is replaying.",
    );
    expect(Notice.messages.at(-1)).not.toContain("failed");
    expect(Notice.messages.at(-1)).not.toContain("retained");
    expect(view.contentEl.textContent).toContain("Replaying");

    transport.graphqlFailureProjection = "applications";
    await refreshCommand?.callback?.();

    expect(Notice.messages.at(-1)).toBe(
      "Ultradex refresh failed. The previous verified snapshot is retained.",
    );
    expect(Notice.messages.join(" ")).not.toContain(
      "Synthetic upstream detail must not reach the monitor",
    );
  });

  test("wires custody through SecretStorage, preserves it on snapshot clear, and defers restored evidence reads until view open", async () => {
    const transport = new RestoredEvidenceTransport();
    transport.setAllFresh();
    const client = createProjectionClient(transport);
    const { app, secretStorage } = createTestApp();
    const custody = JSON.stringify({
      version: 1,
      entries: [
        {
          commandName: "opportunities.create",
          idempotencyKey: "idempotency-main-restored-001",
          correlationId: "correlation-main-restored-001",
          submittedAt: "2026-07-29T17:30:00.000Z",
          contractId: "contract-main-restored-001",
          operationId: "operation-main-restored-001",
          approvalContractId: null,
          state: "succeeded",
        },
      ],
    });
    secretStorage.setSecret(COMMAND_CUSTODY_SECRET_ID, custody);
    class TestUltradexPlugin extends UltradexPlugin {
      clientCreations = 0;

      override createClient(): typeof client {
        this.clientCreations += 1;
        return client;
      }
    }
    const plugin = new TestUltradexPlugin(app as never, {
      id: "ultradex-operator",
      name: "Ultradex Operator",
      version: "0.1.0",
      minAppVersion: "1.11.4",
      description: "Synthetic test manifest",
      author: "Ravenhelm",
    });
    await plugin.onload();
    const hostPlugin = plugin as unknown as Plugin;
    const view = hostPlugin.registeredViews[0]?.creator(
      {},
    ) as UltradexMonitorView;

    expect(plugin.clientCreations).toBe(0);
    expect(transport.requests).toEqual([]);
    expect(hostPlugin.savedData).toEqual([]);

    const clearCommand = hostPlugin.registeredCommands.find(
      ({ id }) => id === "clear-cached-snapshot",
    );
    await clearCommand?.callback?.();
    expect(
      secretStorage.getSecret(COMMAND_CUSTODY_SECRET_ID),
    ).toBe(custody);
    expect(transport.requests).toEqual([]);

    await view.onOpen();
    await vi.waitFor(() => {
      expect(view.contentEl.textContent).toContain(
        "operation-main-restored-001",
      );
      expect(view.contentEl.textContent).toContain(
        syntheticExecutionReceiptEvidence.receiptHash,
      );
    });
    expect(plugin.clientCreations).toBe(2);
    expect(
      transport.requests.filter((request) => {
        const requestBody = JSON.parse(request.body ?? "{}") as {
          readonly query?: string;
        };
        return requestBody.query?.includes("GetOperation");
      }),
    ).toHaveLength(2);
    expect(hostPlugin.savedData).toEqual([]);
  });
});
