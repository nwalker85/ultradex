import {
  syntheticApprovalEvidence,
  syntheticCompletedOperation,
  syntheticExecutionReceiptEvidence,
  syntheticLifecycleEvent,
  syntheticOperation,
  syntheticOutreachPage,
} from "../../../sdk/typescript/tests/fixtures.js";
import {
  UltradexClient,
  type UltradexRequest,
  type UltradexTransport,
  type UltradexTransportResponse,
} from "@ultradex/sdk";
import { afterEach, describe, expect, test, vi } from "vitest";

import { CommandController } from "../src/mutations/command-controller.js";
import { CommandCustodyJournal } from "../src/mutations/command-custody-journal.js";
import { COMMAND_FORMS } from "../src/mutations/command-forms.js";
import { OperationTracker } from "../src/mutations/operation-tracker.js";
import { sanitizeDisplayText } from "../src/sanitize.js";
import type { ObsidianSecretStorage } from "../src/settings.js";
import { UltradexMonitorView } from "../src/views/monitor-view.js";
import { TestElement } from "./obsidian-runtime.js";
import {
  SyntheticProjectionTransport,
  createProjectionStore,
} from "./synthetic-projection-client.js";

function descendants(
  element: TestElement,
  predicate: (candidate: TestElement) => boolean,
): TestElement[] {
  return [
    ...(predicate(element) ? [element] : []),
    ...element.children.flatMap((child) => descendants(child, predicate)),
  ];
}

function byTag(element: TestElement, tagName: string): TestElement[] {
  return descendants(element, (candidate) => candidate.tagName === tagName);
}

function buttonByLabel(
  element: TestElement,
  label: string,
): TestElement | undefined {
  return descendants(
    element,
    (candidate) =>
      candidate.tagName === "button" &&
      candidate.getAttribute("aria-label") === label,
  )[0];
}

function byAttribute(
  element: TestElement,
  name: string,
  value: string,
): TestElement | undefined {
  return descendants(
    element,
    (candidate) => candidate.getAttribute(name) === value,
  )[0];
}

function byClass(
  element: TestElement,
  className: string,
): TestElement | undefined {
  return descendants(element, (candidate) =>
    candidate.className.split(/\s+/u).includes(className),
  )[0];
}

class MonitorCommandTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    return {
      status: 202,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contract_id: "contract-monitor-synthetic-001",
        operation_id: "operation-monitor-synthetic-001",
        status: "accepted",
        submitted_at: "2026-07-29T16:05:00+00:00",
        correlation_id: "correlation-monitor-synthetic-001",
        refusal_code: null,
        refusal_reason: null,
        expires_at: null,
        status_url: "/operations/operation-monitor-synthetic-001",
        events_url: "/operations/operation-monitor-synthetic-001/events",
      }),
    };
  }
}

class MonitorPollingTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    if (!request.url.endsWith("/api/graphql")) {
      return new MonitorCommandTransport().request(request);
    }
    const body = JSON.parse(request.body ?? "{}") as {
      readonly query?: string;
      readonly variables?: Readonly<Record<string, unknown>>;
    };
    const operationId = String(
      body.variables?.id ?? body.variables?.operationId,
    );
    const data = body.query?.includes("GetOperationEvents")
      ? {
          events: [
            {
              id: 501,
              operationId,
              eventType: "synthetic.operation.running",
              timestamp: "2026-07-29T16:11:00+00:00",
              payload: { lifecycleState: "running" },
            },
          ],
        }
      : {
          operation: {
            id: operationId,
            correlationId: "correlation-monitor-synthetic-001",
            command: "opportunities.create",
            status: "running",
            createdAt: "2026-07-29T16:05:00+00:00",
            startedAt: "2026-07-29T16:06:00+00:00",
            completedAt: null,
            result: null,
            error: null,
            freshness: null,
          },
        };
    return {
      status: 200,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ data }),
    };
  }
}

class MonitorTerminalTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];
  receiptAvailable = true;

  constructor(private readonly refused = false) {}

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    if (!request.url.endsWith("/api/graphql")) {
      return {
        status: this.refused ? 503 : 202,
        headers: { "content-type": "application/json" },
        body: JSON.stringify(
          this.refused
            ? {
                contract_id: "contract-monitor-refused-001",
                operation_id: "operation-monitor-refused-001",
                status: "refused",
                submitted_at: "2026-07-29T16:12:00+00:00",
                correlation_id: "correlation-monitor-refused-001",
                refusal_code: "synthetic_policy_denied",
                refusal_reason:
                  "Synthetic policy did not authorize this operation",
                expires_at: null,
                status_url: null,
                events_url: null,
              }
            : {
                contract_id: "contract-monitor-completed-001",
                operation_id: "operation-synthetic-completed-001",
                status: "accepted",
                submitted_at: "2026-07-29T16:12:00+00:00",
                correlation_id: "correlation-monitor-completed-001",
                refusal_code: null,
                refusal_reason: null,
                expires_at: null,
                status_url: null,
                events_url: null,
              },
        ),
      };
    }
    const body = JSON.parse(request.body ?? "{}") as {
      readonly query?: string;
      readonly variables?: Readonly<Record<string, unknown>>;
    };
    const operationId = String(
      body.variables?.id ?? body.variables?.operationId,
    );
    const data = body.query?.includes("GetOperationEvents")
      ? {
          events: [
            {
              ...syntheticLifecycleEvent,
              operationId,
            },
          ],
        }
      : body.query?.includes("GetApproval")
        ? {
            approval: syntheticApprovalEvidence,
          }
        : body.query?.includes("GetExecutionReceipt")
        ? {
            executionReceipt: this.receiptAvailable
              ? {
                  ...syntheticExecutionReceiptEvidence,
                  operationId,
                }
              : null,
          }
        : {
            operation: {
              ...syntheticCompletedOperation,
              id: operationId,
              correlationId: "correlation-monitor-completed-001",
            },
          };
    return {
      status: 200,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ data }),
    };
  }
}

class MonitorStatusTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];

  constructor(private readonly status: "pending" | "running") {}

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    return {
      status: 202,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contract_id: `contract-monitor-${this.status}-001`,
        operation_id: `operation-monitor-${this.status}-001`,
        status: this.status,
        submitted_at: "2026-07-29T17:20:00+00:00",
        correlation_id: `correlation-monitor-${this.status}-001`,
        refusal_code: null,
        refusal_reason: null,
        expires_at: null,
        status_url: null,
        events_url: null,
      }),
    };
  }
}

class GatedMonitorCommandTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];
  release: (() => void) | null = null;
  private readonly gate = new Promise<void>((resolve) => {
    this.release = resolve;
  });

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    if (request.url.endsWith("/api/graphql")) {
      throw new Error("Detached command must not begin evidence reads");
    }
    await this.gate;
    return new MonitorCommandTransport().request(request);
  }
}

class RefreshGateTransport extends MonitorPollingTransport {
  blockReads = false;
  release: (() => void) | null = null;
  private readonly gate = new Promise<void>((resolve) => {
    this.release = resolve;
  });

  override async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    if (
      this.blockReads &&
      request.url.endsWith("/api/graphql")
    ) {
      this.requests.push(request);
      await this.gate;
      const body = JSON.parse(request.body ?? "{}") as {
        readonly query?: string;
        readonly variables?: Readonly<Record<string, unknown>>;
      };
      const operationId = String(
        body.variables?.id ?? body.variables?.operationId,
      );
      const data = body.query?.includes("GetOperationEvents")
        ? {
            events: [
              {
                ...syntheticLifecycleEvent,
                operationId,
              },
            ],
          }
        : {
            operation: {
              id: operationId,
              correlationId: "correlation-monitor-synthetic-001",
              command: "opportunities.create",
              status: "running",
              createdAt: "2026-07-29T16:05:00+00:00",
              startedAt: "2026-07-29T16:06:00+00:00",
              completedAt: null,
              result: null,
              error: null,
              freshness: null,
            },
          };
      return {
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ data }),
      };
    }
    return super.request(request);
  }
}

class StagedEvidenceTransport implements UltradexTransport {
  readonly requests: UltradexRequest[] = [];
  operationStatuses: Array<"running" | "completed"> = [
    "running",
    "running",
    "completed",
  ];
  blockNextOperationRead = false;
  release: (() => void) | null = null;
  private readonly gate = new Promise<void>((resolve) => {
    this.release = resolve;
  });

  async request(
    request: UltradexRequest,
  ): Promise<UltradexTransportResponse> {
    this.requests.push(request);
    if (!request.url.endsWith("/api/graphql")) {
      return new MonitorCommandTransport().request(request);
    }
    const body = JSON.parse(request.body ?? "{}") as {
      readonly query?: string;
      readonly variables?: Readonly<Record<string, unknown>>;
    };
    const operationId = String(
      body.variables?.id ?? body.variables?.operationId,
    );
    let data: unknown;
    if (body.query?.includes("GetOperationEvents")) {
      data = {
        events: [
          {
            ...syntheticLifecycleEvent,
            operationId,
          },
        ],
      };
    } else if (body.query?.includes("GetExecutionReceipt")) {
      data = {
        executionReceipt: {
          ...syntheticExecutionReceiptEvidence,
          operationId,
        },
      };
    } else if (body.query?.includes("GetOperation")) {
      if (this.blockNextOperationRead) {
        this.blockNextOperationRead = false;
        await this.gate;
      }
      const status = this.operationStatuses.shift() ?? "completed";
      data = {
        operation:
          status === "completed"
            ? {
                ...syntheticCompletedOperation,
                id: operationId,
              }
            : {
                ...syntheticOperation,
                id: operationId,
                status,
              },
      };
    } else {
      throw new Error("Unexpected staged evidence request");
    }
    return {
      status: 200,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ data }),
    };
  }
}

class MonitorCustodyStorage implements ObsidianSecretStorage {
  private readonly values = new Map<string, string>();

  getSecret(id: string): string | null {
    return this.values.get(id) ?? null;
  }

  setSecret(id: string, secret: string): void {
    this.values.set(id, secret);
  }
}

afterEach(() => {
  vi.useRealTimers();
});

describe("UltradexMonitorView", () => {
  test("opening renders the validated aggregate with accessible native controls and copyable operation IDs", async () => {
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    const store = createProjectionStore(transport);
    const copied: string[] = [];
    const view = new UltradexMonitorView({} as never, store, {
      copyText: async (value) => {
        copied.push(value);
      },
    });

    await view.onOpen();

    const root = view.contentEl as unknown as TestElement;
    expect(transport.requests).toHaveLength(5);
    expect(
      byTag(root, "h2").map((heading) => heading.textContent),
    ).toEqual(["Ultradex operator monitor"]);
    expect(
      byTag(root, "h3").map((heading) => heading.textContent),
    ).toEqual([
      "Opportunities",
      "Applications",
      "Relationships",
      "Outreach",
      "Recent operations",
    ]);
    expect(root.textContent).toContain("Connected");
    expect(root.textContent).toContain("Synthetic Systems");
    expect(root.textContent).toContain("Platform Engineer");
    expect(root.textContent).toContain("Synthetic follow-up");
    expect(root.textContent).toContain("dex-contact-synthetic-001");
    expect(root.textContent).toContain("Qualified");
    expect(root.textContent).toContain("Applied");
    expect(root.textContent).toContain("Approved");
    expect(root.textContent).toContain("Gmail");
    expect(root.textContent).toContain("operation-synthetic-completed-001");
    expect(root.textContent).toContain("correlation-synthetic-completed-001");
    expect(root.textContent).toContain("Fresh");
    expect(root.textContent).toContain("Completed");
    expect(byTag(root, "table")).toHaveLength(5);
    expect(
      byTag(root, "th").every(
        (header) =>
          header.getAttribute("scope") === "col" ||
          header.getAttribute("scope") === "row",
      ),
    ).toBe(true);
    expect(
      byTag(root, "button").every(
        (button) =>
          button.style.minWidth === "44px" &&
          button.style.minHeight === "44px",
      ),
    ).toBe(true);

    const operationCopyButton = buttonByLabel(
      root,
      "Copy operation ID operation-synthetic-completed-001",
    );
    const correlationCopyButton = buttonByLabel(
      root,
      "Copy correlation ID correlation-synthetic-completed-001",
    );
    operationCopyButton?.click();
    correlationCopyButton?.click();
    await Promise.resolve();

    expect(copied).toEqual([
      "operation-synthetic-completed-001",
      "correlation-synthetic-completed-001",
    ]);
    expect(operationCopyButton?.getAttribute("aria-live")).toBe(
      "polite",
    );
    expect(operationCopyButton?.getAttribute("aria-label")).toBe(
      "Copied operation ID operation-synthetic-completed-001",
    );
    expect(correlationCopyButton?.getAttribute("aria-label")).toBe(
      "Copied correlation ID correlation-synthetic-completed-001",
    );

    buttonByLabel(root, "Refresh projections")?.click();
    expect(transport.requests).toHaveLength(10);
  });

  test("connection strip shows only the sanitized configured service origin", async () => {
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    const view = new UltradexMonitorView(
      {} as never,
      createProjectionStore(transport),
      {
        baseUrl: () =>
          "https://operator:base-secret@synthetic.invalid/private/path?token=query-secret#fragment-secret",
      },
    );

    await view.onOpen();

    const connection = byClass(
      view.contentEl as unknown as TestElement,
      "ultradex-connection",
    );
    expect(connection?.textContent).toContain(
      "https://synthetic.invalid",
    );
    expect(connection?.textContent).not.toContain("operator");
    expect(connection?.textContent).not.toContain("base-secret");
    expect(connection?.textContent).not.toContain("private/path");
    expect(connection?.textContent).not.toContain("query-secret");
    expect(connection?.textContent).not.toContain("fragment-secret");
  });

  test("copy failures provide sanitized accessible feedback", async () => {
    const transport = new SyntheticProjectionTransport();
    transport.setAllFresh();
    const view = new UltradexMonitorView(
      {} as never,
      createProjectionStore(transport),
      {
        copyText: async () => {
          throw new Error("Synthetic clipboard detail");
        },
      },
    );
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;
    const operationCopyButton = buttonByLabel(
      root,
      "Copy operation ID operation-synthetic-completed-001",
    );

    operationCopyButton?.click();
    await Promise.resolve();

    expect(operationCopyButton?.textContent).toBe("Copy failed");
    expect(operationCopyButton?.getAttribute("aria-label")).toBe(
      "Copy failed for operation ID operation-synthetic-completed-001",
    );
    expect(root.textContent).not.toContain("Synthetic clipboard detail");
  });

  test("loading, authentication, stale, and empty states never masquerade as fresh zero counts", async () => {
    let releaseRequests: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      releaseRequests = resolve;
    });
    const loadingTransport = new SyntheticProjectionTransport(gate);
    const loadingView = new UltradexMonitorView(
      {} as never,
      createProjectionStore(loadingTransport),
    );

    const opening = loadingView.onOpen();
    expect(
      (loadingView.contentEl as unknown as TestElement).textContent,
    ).toContain("Loading verified projections");
    releaseRequests?.();
    await opening;

    const authTransport = new SyntheticProjectionTransport();
    authTransport.failureMode = "authentication";
    const authView = new UltradexMonitorView(
      {} as never,
      createProjectionStore(authTransport),
    );
    await authView.onOpen();
    const authText = (authView.contentEl as unknown as TestElement).textContent;
    expect(authText).toContain("Authentication required");
    expect(authText).toContain("Open Ultradex Operator settings");
    expect(authText).not.toContain("0 opportunities");
    expect(byTag(authView.contentEl as unknown as TestElement, "table")).toEqual(
      [],
    );

    const staleTransport = new SyntheticProjectionTransport();
    const staleStore = createProjectionStore(staleTransport);
    const staleView = new UltradexMonitorView({} as never, staleStore);
    await staleView.onOpen();
    staleTransport.schemaFailureProjection = "relationships";
    await staleStore.refresh();
    const staleText =
      (staleView.contentEl as unknown as TestElement).textContent;
    expect(staleText).toContain("Stale snapshot");
    expect(staleText).toContain("Projection contract mismatch");
    expect(staleText).toContain("Synthetic Systems");
    expect(staleText).not.toContain("nextCursor");
    expect(staleText).not.toContain("Zod");

    staleTransport.schemaFailureProjection = null;
    staleTransport.graphqlFailureProjection = "outreach";
    await staleStore.refresh();
    const graphqlText =
      (staleView.contentEl as unknown as TestElement).textContent;
    expect(graphqlText).toContain("Outreach projection failed validation");
    expect(graphqlText).not.toContain(
      "Synthetic upstream detail must not reach the monitor",
    );

    const emptyTransport = new SyntheticProjectionTransport();
    emptyTransport.emptyProjection = true;
    const emptyView = new UltradexMonitorView(
      {} as never,
      createProjectionStore(emptyTransport),
    );
    await emptyView.onOpen();
    const emptyText =
      (emptyView.contentEl as unknown as TestElement).textContent;
    expect(emptyText).toContain("No opportunities in the current projection");
    expect(emptyText).toContain("No applications in the current projection");
    expect(emptyText).toContain("No relationships in the current projection");
    expect(emptyText).toContain("No outreach in the current projection");
    expect(emptyText).toContain("No recent operations");
  });

  test("schema guidance claims retention only when a previous verified snapshot exists", async () => {
    const initialFailureTransport = new SyntheticProjectionTransport();
    initialFailureTransport.schemaFailureProjection = "opportunities";
    const initialFailureView = new UltradexMonitorView(
      {} as never,
      createProjectionStore(initialFailureTransport),
    );
    await initialFailureView.onOpen();
    const initialFailureText = (
      initialFailureView.contentEl as unknown as TestElement
    ).textContent;

    expect(initialFailureText).toContain(
      "Opportunities projection failed validation",
    );
    expect(initialFailureText).not.toContain(
      "previous verified snapshot is retained",
    );

    const retainedTransport = new SyntheticProjectionTransport();
    retainedTransport.setAllFresh();
    const retainedStore = createProjectionStore(retainedTransport);
    const retainedView = new UltradexMonitorView(
      {} as never,
      retainedStore,
    );
    await retainedView.onOpen();
    retainedTransport.schemaFailureProjection = "opportunities";
    await retainedStore.refresh();
    const retainedText = (
      retainedView.contentEl as unknown as TestElement
    ).textContent;

    expect(retainedText).toContain(
      "Opportunities projection failed validation",
    );
    expect(retainedText).toContain(
      "previous verified snapshot is retained",
    );
  });

  test("closing detaches rendering and display text removes invisible control characters", async () => {
    const transport = new SyntheticProjectionTransport();
    const store = createProjectionStore(transport);
    const view = new UltradexMonitorView({} as never, store);
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;
    const renderedText = root.textContent;

    await view.onClose();
    store.clear();

    expect(root.textContent).toBe(renderedText);
    expect(
      sanitizeDisplayText(
        "  Synthetic\u202E role\u0000\n\tstate  ",
        "Unavailable",
        80,
      ),
    ).toBe("Synthetic role state");
    expect(sanitizeDisplayText(null, "Unavailable", 80)).toBe("Unavailable");
    expect(sanitizeDisplayText("Synthetic", "Unavailable", 6)).toBe(
      "Synth…",
    );
  });

  test("nine native command forms reveal consequence and idempotency evidence before confirmation", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const commandTransport = new MonitorCommandTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport: commandTransport,
      }),
      projectionStore: store,
      createId: (kind) =>
        kind === "idempotency"
          ? "idempotency-monitor-synthetic-001"
          : "correlation-monitor-synthetic-001",
      now: () => new Date("2026-07-29T16:05:00.000Z"),
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;

    expect(
      descendants(
        root,
        (candidate) =>
          candidate.tagName === "form" &&
          candidate.getAttribute("data-command") !== null,
      ),
    ).toHaveLength(9);
    const form = byAttribute(
      root,
      "data-command",
      "opportunities.create",
    );
    const employer = byAttribute(form ?? root, "name", "employer");
    const title = byAttribute(form ?? root, "name", "title");
    const evidence = byAttribute(
      form ?? root,
      "name",
      "sourceEvidenceId",
    );
    (employer as unknown as HTMLInputElement).value = "Synthetic Systems";
    (title as unknown as HTMLInputElement).value = "Platform Engineer";
    (evidence as unknown as HTMLInputElement).value =
      "evidence-synthetic-001";
    await form?.eventListeners.submit?.[0]?.({
      preventDefault(): void {},
    });

    expect(commandTransport.requests).toEqual([]);
    expect(root.textContent).toContain(
      "Create a new opportunity record in Ultradex.",
    );
    expect(root.textContent).toContain(
      "idempotency-monitor-synthetic-001",
    );
    expect(root.textContent).toContain(
      "correlation-monitor-synthetic-001",
    );

    buttonByLabel(root, "Confirm Create opportunity")?.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(commandTransport.requests).toHaveLength(1);
  });

  test("every confirmation renders the exact sanitized bound fields and outreach approval adds the projected channel", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    projectionTransport.outreachItemsOverride = [
      {
        ...syntheticOutreachPage.items[0],
        status: "pending_approval",
        approvalContractId: null,
      },
    ];
    const store = createProjectionStore(projectionTransport);
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport: new MonitorCommandTransport(),
      }),
      projectionStore: store,
      createId: (kind) => `${kind}-monitor-review-001`,
      now: () => new Date("2026-07-29T17:15:00.000Z"),
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;
    const commitment =
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const reviews = [
      [
        COMMAND_FORMS.sourcesIngest.create({
          sourceKind: "manual",
          sourceRef: "source-synthetic-001",
          observedAt: "2026-07-29T17:15:00Z",
        }),
        [
          "Source kind",
          "manual",
          "Opaque source reference",
          "source-synthetic-001",
          "Observed at",
          "2026-07-29T17:15:00Z",
        ],
      ],
      [
        COMMAND_FORMS.opportunityCreate.create({
          employer: "Synthetic\u202E Systems",
          title: "Platform Engineer",
          sourceEvidenceId: "evidence-synthetic-001",
        }),
        [
          "Employer",
          "Synthetic Systems",
          "Role title",
          "Platform Engineer",
          "Source evidence ID",
          "evidence-synthetic-001",
        ],
      ],
      [
        COMMAND_FORMS.opportunityScore.create({
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        }),
        [
          "Opportunity ID",
          "opportunity-synthetic-001",
          "Scoring lens",
          "executive",
        ],
      ],
      [
        COMMAND_FORMS.applicationTransition.create({
          applicationId: "application-synthetic-001",
          status: "interviewing",
          occurredAt: "2026-07-29T17:16:00+00:00",
        }),
        [
          "Application ID",
          "application-synthetic-001",
          "New state",
          "interviewing",
          "Occurred at",
          "2026-07-29T17:16:00+00:00",
        ],
      ],
      [
        COMMAND_FORMS.relationshipSync.create({
          opportunityId: "opportunity-synthetic-001",
          dexContactRef: "dex-synthetic-001",
        }),
        [
          "Opportunity ID",
          "opportunity-synthetic-001",
          "Opaque Dex contact reference",
          "dex-synthetic-001",
        ],
      ],
      [
        COMMAND_FORMS.outreachPrepare.create({
          opportunityId: "opportunity-synthetic-001",
          channel: "linkedin",
          messageCommitment: commitment,
          relationshipId: "relationship-synthetic-001",
        }),
        [
          "Opportunity ID",
          "opportunity-synthetic-001",
          "Channel",
          "linkedin",
          "Message commitment",
          commitment,
          "Relationship ID",
          "relationship-synthetic-001",
        ],
      ],
      [
        COMMAND_FORMS.outreachApprove.create({
          outreachId: "outreach-synthetic-001",
          messageCommitment: commitment,
        }),
        [
          "Outreach ID",
          "outreach-synthetic-001",
          "Message commitment",
          commitment,
          "Channel",
          "gmail",
        ],
      ],
      [
        COMMAND_FORMS.outreachSend.create({
          outreachId: "outreach-synthetic-001",
          approvalContractId: "approval-synthetic-001",
          messageCommitment: commitment,
          channel: "linkedin",
        }),
        [
          "Outreach ID",
          "outreach-synthetic-001",
          "Exact approval contract ID",
          "approval-synthetic-001",
          "Message commitment",
          commitment,
          "Channel",
          "linkedin",
        ],
      ],
      [
        COMMAND_FORMS.evidenceExport.create({
          subjectType: "opportunity",
          subjectId: "opportunity-synthetic-001",
          profile: "accountability.v1",
        }),
        [
          "Subject type",
          "opportunity",
          "Subject ID",
          "opportunity-synthetic-001",
          "Export profile",
          "accountability.v1",
        ],
      ],
    ] as const;

    for (const [draft, expectedValues] of reviews) {
      controller.prepare(draft);
      const review = byClass(root, "ultradex-command-review");
      expect(review?.getAttribute("aria-live")).toBe("polite");
      for (const expectedValue of expectedValues) {
        expect(review?.textContent).toContain(expectedValue);
      }
      expect(review?.textContent).not.toContain("\u202E");
    }
  });

  test("outreach send exposes the exact approval mandate before its second confirmation", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const commandTransport = new MonitorCommandTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport: commandTransport,
      }),
      projectionStore: store,
      createId: (kind) => `${kind}-monitor-send-001`,
      now: () => new Date("2026-07-29T16:06:00.000Z"),
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;
    const form = byAttribute(root, "data-command", "outreach.send");
    const commitment =
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    for (const [name, value] of [
      ["outreachId", "outreach-synthetic-001"],
      ["approvalContractId", "approval-synthetic-exact-001"],
      ["messageCommitment", commitment],
      ["channel", "linkedin"],
    ] as const) {
      (
        byAttribute(form ?? root, "name", name) as unknown as
          | HTMLInputElement
          | HTMLSelectElement
      ).value = value;
    }
    await form?.eventListeners.submit?.[0]?.({
      preventDefault(): void {},
    });

    const firstReview = byClass(root, "ultradex-command-review");
    expect(firstReview?.textContent).toContain("outreach-synthetic-001");
    expect(firstReview?.textContent).toContain(commitment);
    expect(firstReview?.textContent).toContain("linkedin");
    expect(firstReview?.textContent).toContain(
      "approval-synthetic-exact-001",
    );

    buttonByLabel(root, "Confirm Send outreach")?.click();
    await Promise.resolve();
    expect(commandTransport.requests).toEqual([]);
    expect(root.textContent).toContain(
      "approval-synthetic-exact-001",
    );
    expect(root.textContent).toContain("outreach-synthetic-001");
    expect(root.textContent).toContain(commitment);
    expect(root.textContent).toContain("linkedin");

    buttonByLabel(
      root,
      "Confirm approval-bound send approval-synthetic-exact-001",
    )?.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(commandTransport.requests).toHaveLength(1);
  });

  test("outreach approval form shows safe refresh guidance when no exact pending binding exists", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const commandTransport = new MonitorCommandTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport: commandTransport,
      }),
      projectionStore: store,
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;
    const form = byAttribute(root, "data-command", "outreach.approve");
    (
      byAttribute(form ?? root, "name", "outreachId") as TestElement
    ).value = "outreach-synthetic-001";
    (
      byAttribute(
        form ?? root,
        "name",
        "messageCommitment",
      ) as TestElement
    ).value =
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    await form?.eventListeners.submit?.[0]?.({
      preventDefault(): void {},
    });

    expect(form?.textContent).toContain(
      "The verified outreach binding does not match this approval request. Refresh projections and review it again.",
    );
    expect(controller.getState().confirmation).toBeNull();
    expect(commandTransport.requests).toEqual([]);
    expect(form?.textContent).not.toContain("synthetic-secret");
  });

  test("known terminal outcome remains refreshable when only evidence is unverifiable", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const mutationTransport = new MonitorTerminalTransport();
    mutationTransport.receiptAvailable = false;
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: mutationTransport,
    });
    const controller = new CommandController({
      client,
      projectionStore: store,
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 1,
        pollIntervalMs: 1,
      }),
      createId: (kind) => `${kind}-monitor-evidence-status-001`,
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );

    await controller.confirm(confirmation.id);

    const root = view.contentEl as unknown as TestElement;
    const card = byAttribute(root, "data-state", "succeeded");
    expect(card?.getAttribute("data-evidence-status")).toBe(
      "unverifiable",
    );
    expect(card?.textContent).toContain("Evidence statusUnverifiable");
    expect(
      buttonByLabel(
        card ?? root,
        "Refresh operation evidence operation-synthetic-completed-001",
      ),
    ).toBeDefined();

    mutationTransport.receiptAvailable = true;
    buttonByLabel(
      card ?? root,
      "Refresh operation evidence operation-synthetic-completed-001",
    )?.click();
    await vi.waitFor(() => {
      const recovered = byAttribute(root, "data-state", "succeeded");
      expect(recovered?.getAttribute("data-evidence-status")).toBe(
        "complete",
      );
    });
  });

  test("manual refresh stays available through pending evidence until exact terminal evidence completes", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const mutationTransport = new StagedEvidenceTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: mutationTransport,
    });
    const custody = new CommandCustodyJournal(
      new MonitorCustodyStorage(),
    );
    const controller = new CommandController({
      client,
      projectionStore: store,
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 1,
        pollIntervalMs: 1,
      }),
      journal: custody,
      createId: (kind) => `${kind}-staged-evidence-001`,
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );
    await controller.confirm(confirmation.id);
    const root = view.contentEl as unknown as TestElement;
    const operationId = "operation-monitor-synthetic-001";
    const commandWrites = (): readonly UltradexRequest[] =>
      mutationTransport.requests.filter(
        (request) => !request.url.endsWith("/api/graphql"),
      );

    expect(controller.getState().records[0]).toMatchObject({
      state: "unverifiable",
      evidenceStatus: "unverifiable",
    });
    const firstRefresh = buttonByLabel(
      root,
      `Refresh operation evidence ${operationId}`,
    );
    expect(firstRefresh).toBeDefined();

    mutationTransport.blockNextOperationRead = true;
    firstRefresh?.click();
    firstRefresh?.click();
    await vi.waitFor(() => {
      const refreshing = buttonByLabel(
        root,
        `Refreshing operation evidence ${operationId}`,
      );
      expect(refreshing?.disabled).toBe(true);
      expect(refreshing?.textContent).toBe("Refreshing evidence…");
    });
    expect(commandWrites()).toHaveLength(1);

    mutationTransport.release?.();
    await vi.waitFor(() => {
      expect(controller.getState().records[0]).toMatchObject({
        state: "running",
        evidenceStatus: "pending",
      });
      expect(controller.getState().refreshingRecordIds).toEqual([]);
    });
    const pendingRefresh = buttonByLabel(
      root,
      `Refresh operation evidence ${operationId}`,
    );
    expect(pendingRefresh?.disabled).toBe(false);
    expect(pendingRefresh?.textContent).toBe(
      "Refresh operation evidence",
    );

    pendingRefresh?.click();
    pendingRefresh?.click();
    await vi.waitFor(() => {
      expect(controller.getState().records[0]).toMatchObject({
        state: "succeeded",
        evidenceStatus: "complete",
      });
    });

    expect(
      buttonByLabel(
        root,
        `Refresh operation evidence ${operationId}`,
      ),
    ).toBeUndefined();
    expect(commandWrites()).toHaveLength(1);
    expect(custody.load()).toHaveLength(1);
  });

  test("manual evidence refresh is visibly single-flight and lifecycle event IDs are copyable without payload disclosure", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const mutationTransport = new RefreshGateTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: mutationTransport,
    });
    const controller = new CommandController({
      client,
      projectionStore: store,
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 1,
        pollIntervalMs: 1,
      }),
      createId: (kind) => `${kind}-monitor-refresh-001`,
      now: () => new Date("2026-07-29T17:18:00.000Z"),
    });
    const copied: string[] = [];
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
      copyText: async (value) => {
        copied.push(value);
      },
    });
    await view.onOpen();
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );
    await controller.confirm(confirmation.id);
    const root = view.contentEl as unknown as TestElement;
    const operationId = "operation-monitor-synthetic-001";

    expect(root.textContent).toContain("Event ID");
    expect(root.textContent).toContain("501");
    expect(root.textContent).not.toContain("lifecycleState");
    buttonByLabel(root, "Copy event ID 501")?.click();
    await Promise.resolve();
    expect(copied).toEqual(["501"]);

    mutationTransport.blockReads = true;
    const requestsBeforeRefresh = mutationTransport.requests.length;
    const refreshButton = buttonByLabel(
      root,
      `Refresh operation evidence ${operationId}`,
    );
    refreshButton?.click();
    refreshButton?.click();
    await Promise.resolve();

    expect(mutationTransport.requests).toHaveLength(
      requestsBeforeRefresh + 1,
    );
    const refreshingButton = buttonByLabel(
      root,
      `Refreshing operation evidence ${operationId}`,
    );
    expect(refreshingButton?.disabled).toBe(true);
    expect(refreshingButton?.textContent).toBe("Refreshing evidence…");

    mutationTransport.release?.();
    await vi.waitFor(() => {
      expect(mutationTransport.requests).toHaveLength(
        requestsBeforeRefresh + 2,
      );
    });
  });

  test("preserves a partially entered form draft and logical focus across store, controller, and polling rerenders", async () => {
    vi.useFakeTimers();
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const mutationTransport = new MonitorPollingTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: mutationTransport,
    });
    const controller = new CommandController({
      client,
      projectionStore: store,
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 2,
        pollIntervalMs: 1_000,
      }),
      createId: (kind) => `${kind}-monitor-draft-001`,
      now: () => new Date("2026-07-29T17:18:30.000Z"),
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;
    const employerControl = (): TestElement =>
      byAttribute(
        byAttribute(root, "data-command", "opportunities.create") ??
          root,
        "name",
        "employer",
      ) as TestElement;
    const expectDraftAndFocus = (): void => {
      expect(employerControl().value).toBe("Partially entered employer");
      expect(
        root.ownerDocument.activeElement?.getAttribute("name"),
      ).toBe("employer");
    };

    employerControl().value = "Partially entered employer";
    await employerControl().eventListeners.input?.[0]?.({
      type: "input",
      target: employerControl(),
    });
    employerControl().focus();

    await store.refresh();
    expectDraftAndFocus();

    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );
    expectDraftAndFocus();

    const submission = controller.confirm(confirmation.id);
    await vi.advanceTimersByTimeAsync(0);
    expectDraftAndFocus();
    await vi.advanceTimersByTimeAsync(1_000);
    await submission;
    expectDraftAndFocus();

    await view.onClose();
  });

  test("preserves logical focus, moves confirmation before the form grid, and announces submitting and new outcomes", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const mutationTransport = new GatedMonitorCommandTransport();
    const controller = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport: mutationTransport,
      }),
      projectionStore: store,
      createId: (kind) => `${kind}-monitor-focus-001`,
      now: () => new Date("2026-07-29T17:19:00.000Z"),
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const root = view.contentEl as unknown as TestElement;
    const sourceReference = byAttribute(
      byAttribute(root, "data-command", "sources.ingest") ?? root,
      "name",
      "sourceRef",
    );
    sourceReference?.focus();
    await store.refresh();
    expect(root.ownerDocument.activeElement?.getAttribute("name")).toBe(
      "sourceRef",
    );

    const form = byAttribute(root, "data-command", "opportunities.create");
    (
      byAttribute(form ?? root, "name", "employer") as TestElement
    ).value = "Synthetic Systems";
    (byAttribute(form ?? root, "name", "title") as TestElement).value =
      "Platform Engineer";
    (
      byAttribute(
        form ?? root,
        "name",
        "sourceEvidenceId",
      ) as TestElement
    ).value = "evidence-synthetic-001";
    const reviewAction = buttonByLabel(
      form ?? root,
      "Review Create opportunity",
    );
    reviewAction?.focus();
    await form?.eventListeners.submit?.[0]?.({
      preventDefault(): void {},
    });

    expect(
      root.ownerDocument.activeElement?.getAttribute("aria-label"),
    ).toBe("Confirm Create opportunity");
    const confirmationSection = byClass(
      root,
      "ultradex-command-review",
    );
    const formsSection = byClass(root, "ultradex-command-bar");
    const monitor = byClass(root, "ultradex-monitor");
    expect(
      monitor?.children.indexOf(confirmationSection!) ?? -1,
    ).toBeLessThan(
      monitor?.children.indexOf(formsSection!) ?? -1,
    );
    expect(confirmationSection?.getAttribute("aria-live")).toBe(
      "polite",
    );

    buttonByLabel(root, "Confirm Create opportunity")?.click();
    await Promise.resolve();
    const submitting = byClass(root, "ultradex-command-review");
    expect(submitting?.textContent).toContain("Submitting");
    expect(submitting?.getAttribute("aria-live")).toBe("polite");

    mutationTransport.release?.();
    await vi.waitFor(() => {
      const outcomes = byClass(root, "ultradex-governed-outcomes");
      expect(outcomes?.getAttribute("aria-live")).toBe("polite");
      expect(outcomes?.textContent).toContain("Accepted");
    });
  });

  test("closing during an in-flight command allows only custody completion and never starts reads or mutates detached DOM", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const mutationTransport = new GatedMonitorCommandTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: mutationTransport,
    });
    const controller = new CommandController({
      client,
      projectionStore: store,
      operationTracker: new OperationTracker(client),
      createId: (kind) => `${kind}-monitor-inflight-close-001`,
      now: () => new Date("2026-07-29T17:20:00.000Z"),
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );
    const submission = controller.confirm(confirmation.id);
    await Promise.resolve();
    await view.onClose();
    const detachedText = view.contentEl.textContent;

    mutationTransport.release?.();
    await submission;

    expect(mutationTransport.requests).toHaveLength(1);
    expect(view.contentEl.textContent).toBe(detachedText);
  });

  test.each(["pending", "running"] as const)(
    "renders %s as its own governed outcome label and data state",
    async (status) => {
      const projectionTransport = new SyntheticProjectionTransport();
      projectionTransport.setAllFresh();
      const store = createProjectionStore(projectionTransport);
      const controller = new CommandController({
        client: new UltradexClient({
          baseUrl: "https://synthetic.invalid",
          token: "synthetic-secret-value",
          transport: new MonitorStatusTransport(status),
        }),
        projectionStore: store,
        createId: (kind) => `${kind}-monitor-${status}-001`,
        now: () => new Date("2026-07-29T17:21:00.000Z"),
      });
      const view = new UltradexMonitorView({} as never, store, {
        commandController: controller,
      });
      await view.onOpen();
      const confirmation = controller.prepare(
        COMMAND_FORMS.opportunityScore.create({
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        }),
      );

      await controller.confirm(confirmation.id);

      const card = byAttribute(
        view.contentEl as unknown as TestElement,
        "data-state",
        status,
      );
      expect(card?.textContent).toContain(
        status === "pending" ? "Pending" : "Running",
      );
    },
  );

  test("closing the view stops lifecycle timers and prevents late UI mutation", async () => {
    vi.useFakeTimers();
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    const mutationTransport = new MonitorPollingTransport();
    const client = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: mutationTransport,
    });
    const controller = new CommandController({
      client,
      projectionStore: store,
      operationTracker: new OperationTracker(client, {
        maxPollAttempts: 5,
        pollIntervalMs: 1_000,
      }),
      createId: (kind) => `${kind}-monitor-close-001`,
      now: () => new Date("2026-07-29T16:11:00.000Z"),
    });
    const view = new UltradexMonitorView({} as never, store, {
      commandController: controller,
    });
    await view.onOpen();
    const confirmation = controller.prepare(
      COMMAND_FORMS.opportunityCreate.create({
        employer: "Synthetic Systems",
        title: "Platform Engineer",
        sourceEvidenceId: "evidence-synthetic-001",
      }),
    );
    const submission = controller.confirm(confirmation.id);
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(1);

    await view.onClose();
    const detachedText = view.contentEl.textContent;

    expect(vi.getTimerCount()).toBe(0);
    await submission;
    await vi.runAllTimersAsync();
    expect(view.contentEl.textContent).toBe(detachedText);
  });

  test("governed cards preserve refusal evidence and label terminal receipts as server-recorded only", async () => {
    const projectionTransport = new SyntheticProjectionTransport();
    projectionTransport.setAllFresh();
    const store = createProjectionStore(projectionTransport);
    await store.refresh();

    const refusedTransport = new MonitorTerminalTransport(true);
    const refusedController = new CommandController({
      client: new UltradexClient({
        baseUrl: "https://synthetic.invalid",
        token: "synthetic-secret-value",
        transport: refusedTransport,
      }),
      projectionStore: store,
      createId: (kind) => `${kind}-monitor-refused-001`,
      now: () => new Date("2026-07-29T16:12:00.000Z"),
    });
    const refusedView = new UltradexMonitorView({} as never, store, {
      commandController: refusedController,
    });
    await refusedView.onOpen();
    const refusedConfirmation = refusedController.prepare(
      COMMAND_FORMS.opportunityScore.create({
        opportunityId: "opportunity-synthetic-001",
        lens: "executive",
      }),
    );
    await refusedController.confirm(refusedConfirmation.id);
    const refusedText = refusedView.contentEl.textContent;

    expect(refusedText).toContain("Refused");
    expect(refusedText).toContain("synthetic_policy_denied");
    expect(refusedText).toContain(
      "Synthetic policy did not authorize this operation",
    );
    expect(refusedText).toContain("operation-monitor-refused-001");
    expect(refusedText).toContain("correlation-monitor-refused-001");
    expect(refusedText).toContain("idempotency-monitor-refused-001");

    const terminalTransport = new MonitorTerminalTransport();
    const terminalClient = new UltradexClient({
      baseUrl: "https://synthetic.invalid",
      token: "synthetic-secret-value",
      transport: terminalTransport,
    });
    const terminalController = new CommandController({
      client: terminalClient,
      projectionStore: store,
      operationTracker: new OperationTracker(terminalClient, {
        maxPollAttempts: 1,
        pollIntervalMs: 1,
      }),
      createId: (kind) => `${kind}-monitor-terminal-001`,
      now: () => new Date("2026-07-29T16:12:00.000Z"),
    });
    const terminalView = new UltradexMonitorView({} as never, store, {
      commandController: terminalController,
    });
    await terminalView.onOpen();
    const terminalConfirmation = terminalController.prepare(
      COMMAND_FORMS.outreachSend.create({
        outreachId: "outreach-synthetic-001",
        approvalContractId: "approval-synthetic-001",
        messageCommitment:
          syntheticApprovalEvidence.messageCommitment,
        channel: "gmail",
      }),
    );
    await terminalController.confirm(terminalConfirmation.id);
    await terminalController.confirmOutreachSend(
      terminalConfirmation.id,
      "approval-synthetic-001",
    );
    const terminalText = terminalView.contentEl.textContent;

    expect(terminalText).toContain("Succeeded");
    expect(terminalText).toContain(
      syntheticApprovalEvidence.outreachId,
    );
    expect(terminalText).toContain(
      syntheticApprovalEvidence.messageCommitment,
    );
    expect(terminalText).toContain(syntheticApprovalEvidence.channel);
    expect(terminalText).toContain("server-recorded");
    expect(terminalText).toContain(
      "Local signature verification is unavailable",
    );
    expect(terminalText).toContain(
      syntheticExecutionReceiptEvidence.receiptHash,
    );
    expect(terminalText).toContain(
      syntheticExecutionReceiptEvidence.payload.signature.key_id,
    );
    expect(terminalText).toContain(
      syntheticExecutionReceiptEvidence.payload.completed_at,
    );
    expect(terminalText).toContain(
      syntheticExecutionReceiptEvidence.receiptId,
    );
    expect(terminalText).not.toContain("signature-verified");
  });
});
