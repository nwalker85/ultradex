import type {
  Application,
  JobSearchCommandName,
  Opportunity,
  Operation,
  Outreach,
  Relationship,
} from "@ultradex/sdk";
import { ItemView, type WorkspaceLeaf } from "obsidian";

import { renderContractState } from "../components/contract-state.js";
import { renderFreshnessBadge } from "../components/freshness-badge.js";
import {
  type ProjectionErrorCategory,
  type ProjectionSnapshot,
  type ProjectionStore,
  type ProjectionStoreState,
} from "../projection-store.js";
import {
  type CommandController,
  isMutationAvailable,
} from "../mutations/command-controller.js";
import { renderCommandForms } from "../mutations/command-forms.js";
import type { GovernedMutationRecord } from "../mutations/operation-tracker.js";
import { sanitizeDisplayText } from "../sanitize.js";

export const ULTRADEX_OPERATOR_VIEW_TYPE = "ultradex-operator-console";

export interface UltradexMonitorViewOptions {
  readonly copyText?: (value: string) => Promise<void>;
  readonly commandController?: CommandController;
  readonly baseUrl?: string | (() => string);
}

const MINIMUM_INTERACTIVE_TARGET = "44px";

function enforceMinimumInteractiveTarget(
  element: HTMLButtonElement,
): void {
  element.style.minHeight = MINIMUM_INTERACTIVE_TARGET;
  element.style.minWidth = MINIMUM_INTERACTIVE_TARGET;
}

const defaultCopyText = async (value: string): Promise<void> => {
  if (
    typeof navigator === "undefined" ||
    navigator.clipboard === undefined
  ) {
    throw new Error("Clipboard access is unavailable");
  }
  await navigator.clipboard.writeText(value);
};

function formatTimestamp(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "Unavailable";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(timestamp);
}

function formatLabel(value: string): string {
  const label = sanitizeDisplayText(value)
    .replace(/[_-]+/gu, " ")
    .toLocaleLowerCase();
  return `${label.charAt(0).toLocaleUpperCase()}${label.slice(1)}`;
}

function configuredServiceOrigin(
  provider: UltradexMonitorViewOptions["baseUrl"],
): string {
  const value =
    typeof provider === "function" ? provider() : provider;
  if (value === undefined) {
    return "Not configured";
  }
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return "Unavailable";
    }
    return `${url.protocol}//${url.host}`;
  } catch {
    return "Unavailable";
  }
}

function errorStateCopy(category: ProjectionErrorCategory): string {
  switch (category) {
    case "authentication":
      return "Authentication required";
    case "offline":
      return "Ultradex is unreachable";
    case "schema":
      return "Projection contract mismatch";
    default:
      return "Projection data is unavailable";
  }
}

function errorGuidance(
  category: ProjectionErrorCategory,
  hasVerifiedSnapshot: boolean,
): string {
  switch (category) {
    case "authentication":
      return "Open Ultradex Operator settings and verify the API token.";
    case "offline":
      return "Check the Ultradex service connection, then refresh.";
    case "schema":
      return hasVerifiedSnapshot
        ? "The previous verified snapshot is retained. Refresh after the service contract is restored."
        : "Refresh after the service contract is restored.";
    default:
      return "Refresh to load a verified projection snapshot.";
  }
}

function failedProjectionCopy(
  state: ProjectionStoreState,
): string | null {
  if (
    state.errorCategory !== "schema" ||
    state.failedProjection === null
  ) {
    return null;
  }
  return `${sanitizeDisplayText(state.failedProjection)} projection failed validation`;
}

function createTable(
  container: HTMLElement,
  caption: string,
  columns: readonly string[],
): HTMLTableSectionElement {
  const table = container.createEl("table", {
    cls: "ultradex-table",
  });
  table.createEl("caption", {
    cls: "ultradex-visually-hidden",
    text: caption,
  });
  const header = table.createEl("thead").createEl("tr");
  for (const column of columns) {
    header.createEl("th", {
      text: column,
      attr: { scope: "col" },
    });
  }
  return table.createEl("tbody");
}

function createPanel(
  container: HTMLElement,
  id: string,
  title: string,
  count: number,
): HTMLElement {
  const panel = container.createEl("section", {
    cls: "ultradex-pipeline-panel",
    attr: { "aria-labelledby": id },
  });
  const headingRow = panel.createDiv({
    cls: "ultradex-pipeline-panel__heading",
  });
  headingRow.createEl("h3", {
    text: title,
    attr: { id },
  });
  headingRow.createSpan({
    cls: "ultradex-pipeline-panel__count",
    text: String(count),
    attr: { "aria-label": `${count} ${title.toLocaleLowerCase()}` },
  });
  return panel;
}

function renderOpportunities(
  container: HTMLElement,
  opportunities: readonly Opportunity[],
): void {
  const panel = createPanel(
    container,
    "ultradex-opportunities-heading",
    "Opportunities",
    opportunities.length,
  );
  if (opportunities.length === 0) {
    panel.createEl("p", {
      cls: "ultradex-empty-state",
      text: "No opportunities in the current projection.",
    });
    return;
  }
  const body = createTable(panel, "Opportunities", [
    "Employer and role",
    "State",
    "Fit",
    "Updated",
  ]);
  for (const opportunity of opportunities) {
    const row = body.createEl("tr");
    const subject = row.createEl("th", { attr: { scope: "row" } });
    subject.createEl("strong", {
      text: sanitizeDisplayText(opportunity.employer),
    });
    subject.createEl("span", {
      text: sanitizeDisplayText(opportunity.title),
    });
    row.createEl("td", {
      text: formatLabel(opportunity.status),
    });
    row.createEl("td", {
      text:
        opportunity.fitScore === null
          ? "Not scored"
          : `${Math.round(opportunity.fitScore)} / 100`,
    });
    row.createEl("td", {
      text: formatTimestamp(opportunity.updatedAt),
    });
  }
}

function renderApplications(
  container: HTMLElement,
  applications: readonly Application[],
): void {
  const panel = createPanel(
    container,
    "ultradex-applications-heading",
    "Applications",
    applications.length,
  );
  if (applications.length === 0) {
    panel.createEl("p", {
      cls: "ultradex-empty-state",
      text: "No applications in the current projection.",
    });
    return;
  }
  const body = createTable(panel, "Applications", [
    "Application",
    "State",
    "Next action",
    "Updated",
  ]);
  for (const application of applications) {
    const row = body.createEl("tr");
    row.createEl("th", {
      text: sanitizeDisplayText(application.applicationId),
      attr: { scope: "row" },
    });
    row.createEl("td", {
      text: formatLabel(application.status),
    });
    row.createEl("td", {
      text: sanitizeDisplayText(application.nextAction, "No next action"),
    });
    row.createEl("td", {
      text: formatTimestamp(application.updatedAt),
    });
  }
}

function renderRelationships(
  container: HTMLElement,
  relationships: readonly Relationship[],
): void {
  const panel = createPanel(
    container,
    "ultradex-relationships-heading",
    "Relationships",
    relationships.length,
  );
  if (relationships.length === 0) {
    panel.createEl("p", {
      cls: "ultradex-empty-state",
      text: "No relationships in the current projection.",
    });
    return;
  }
  const body = createTable(panel, "Relationships", [
    "Contact reference",
    "Relevance",
    "Context",
    "Updated",
  ]);
  for (const relationship of relationships) {
    const row = body.createEl("tr");
    row.createEl("th", {
      text: sanitizeDisplayText(relationship.dexContactRef),
      attr: { scope: "row" },
    });
    row.createEl("td", {
      text:
        relationship.relevanceScore === null
          ? "Not scored"
          : `${Math.round(relationship.relevanceScore)} / 100`,
    });
    row.createEl("td", {
      text: sanitizeDisplayText(
        relationship.relevanceSummary,
        "No relationship context",
      ),
    });
    row.createEl("td", {
      text: formatTimestamp(relationship.updatedAt),
    });
  }
}

function renderOutreach(
  container: HTMLElement,
  outreachItems: readonly Outreach[],
): void {
  const panel = createPanel(
    container,
    "ultradex-outreach-heading",
    "Outreach",
    outreachItems.length,
  );
  if (outreachItems.length === 0) {
    panel.createEl("p", {
      cls: "ultradex-empty-state",
      text: "No outreach in the current projection.",
    });
    return;
  }
  const body = createTable(panel, "Outreach", [
    "Outreach",
    "Channel",
    "State",
    "Updated",
  ]);
  for (const outreach of outreachItems) {
    const row = body.createEl("tr");
    row.createEl("th", {
      text: sanitizeDisplayText(outreach.outreachId),
      attr: { scope: "row" },
    });
    row.createEl("td", {
      text: formatLabel(outreach.channel),
    });
    row.createEl("td", {
      text: formatLabel(outreach.status),
    });
    row.createEl("td", {
      text: formatTimestamp(outreach.updatedAt),
    });
  }
}

export class UltradexMonitorView extends ItemView {
  private readonly copyText: (value: string) => Promise<void>;
  private unsubscribe: (() => void) | null = null;
  private unsubscribeCommands: (() => void) | null = null;
  private readonly commandController: CommandController | undefined;
  private readonly baseUrl: UltradexMonitorViewOptions["baseUrl"];
  private readonly commandDrafts = new Map<
    JobSearchCommandName,
    Record<string, string>
  >();
  private focusAfterRender: string | null = null;
  private opened = false;

  constructor(
    leaf: WorkspaceLeaf,
    private readonly store: ProjectionStore,
    options: UltradexMonitorViewOptions = {},
  ) {
    super(leaf);
    this.copyText = options.copyText ?? defaultCopyText;
    this.commandController = options.commandController;
    this.baseUrl = options.baseUrl;
  }

  getViewType(): string {
    return ULTRADEX_OPERATOR_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "Ultradex operator";
  }

  async onOpen(): Promise<void> {
    this.opened = true;
    this.unsubscribe?.();
    this.unsubscribe = this.store.subscribe(() => {
      this.render();
    });
    this.unsubscribeCommands?.();
    this.unsubscribeCommands =
      this.commandController?.subscribe(() => {
        this.render();
      }) ?? null;
    this.render();
    this.commandController?.startTracking();
    await this.store.refresh();
  }

  async onClose(): Promise<void> {
    this.opened = false;
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.unsubscribeCommands?.();
    this.unsubscribeCommands = null;
    this.commandController?.stopTracking();
    this.commandDrafts.clear();
  }

  private render(): void {
    if (!this.opened) {
      return;
    }
    const focusKey =
      this.focusAfterRender ?? this.currentFocusKey();
    this.focusAfterRender = null;
    const state = this.store.getState();
    this.contentEl.empty();
    const root = this.contentEl.createDiv({
      cls: "ultradex-monitor",
    });
    const titleRow = root.createDiv({ cls: "ultradex-monitor__title" });
    titleRow.createEl("h2", { text: "Ultradex operator monitor" });
    const refreshButton = titleRow.createEl("button", {
      cls: "ultradex-button",
      text: state.status === "refreshing" ? "Refreshing…" : "Refresh",
      type: "button",
      attr: {
        "aria-label": "Refresh projections",
        "data-ultradex-focus": "projection-refresh",
      },
    });
    enforceMinimumInteractiveTarget(refreshButton);
    refreshButton.disabled =
      state.status === "loading" || state.status === "refreshing";
    refreshButton.addEventListener("click", () => {
      void this.store.refresh();
    });

    this.renderConnection(root, state);
    this.renderCommands(root, state);
    if (state.snapshot === null) {
      this.renderUnavailable(root, state);
      this.restoreFocus(focusKey);
      return;
    }

    this.renderFreshness(root, state.snapshot);
    const panels = root.createDiv({
      cls: "ultradex-pipeline-grid",
    });
    renderOpportunities(panels, state.snapshot.opportunities.items);
    renderApplications(panels, state.snapshot.applications.items);
    renderRelationships(panels, state.snapshot.relationships.items);
    renderOutreach(panels, state.snapshot.outreach.items);
    this.renderOperations(root, state.snapshot.operations);
    this.restoreFocus(focusKey);
  }

  private renderCommands(
    root: HTMLElement,
    state: ProjectionStoreState,
  ): void {
    const controller = this.commandController;
    if (controller === undefined) {
      return;
    }
    this.renderMutationRecords(root, controller);
    const confirmation = controller.getState().confirmation;
    if (confirmation !== null) {
      const review = root.createEl("section", {
        cls: "ultradex-command-review",
        attr: {
          "aria-labelledby": "ultradex-command-review-heading",
          "aria-live": "polite",
          "aria-atomic": "true",
        },
      });
      review.createEl("h3", {
        text: `Review ${confirmation.label}`,
        attr: { id: "ultradex-command-review-heading" },
      });
      review.createEl("p", { text: confirmation.consequence });
      const bindings = review.createDiv({
        cls: "ultradex-command-review__bindings",
      });
      for (const field of confirmation.boundFields) {
        bindings.createEl("strong", {
          text: sanitizeDisplayText(field.label, "Field", 80),
        });
        bindings.createEl("code", {
          text: sanitizeDisplayText(field.value, "Not provided", 512),
        });
      }
      review.createEl("strong", { text: "Idempotency key" });
      review.createEl("code", { text: confirmation.idempotencyKey });
      review.createEl("strong", { text: "Correlation ID" });
      review.createEl("code", { text: confirmation.correlationId });
      const isSecondOutreachConfirmation =
        confirmation.stage === "awaiting-second-confirmation" &&
        confirmation.command.commandName === "outreach.send";
      const approvalContractId =
        confirmation.command.commandName === "outreach.send"
          ? confirmation.command.parameters.approvalContractId
          : null;
      if (isSecondOutreachConfirmation && approvalContractId !== null) {
        review.createEl("p", {
          text: "This second confirmation is bound to the exact outreach ID, commitment, channel, and approval contract shown above.",
        });
      }
      if (confirmation.stage === "submitting") {
        review.createEl("p", {
          cls: "ultradex-command-review__submitting",
          text: "Submitting governed command…",
        });
      }
      if (confirmation.bindingError !== null) {
        review.createEl("p", {
          cls: "ultradex-command-review__error",
          text: sanitizeDisplayText(
            confirmation.bindingError,
            "The reviewed projection binding is no longer valid.",
            260,
          ),
        });
      }
      const confirm = review.createEl("button", {
        cls: "ultradex-button",
        text: isSecondOutreachConfirmation
          ? "Confirm approval-bound send"
          : confirmation.stage === "submitting"
            ? "Submitting…"
            : "Confirm",
        type: "button",
        attr: {
          "aria-label":
            isSecondOutreachConfirmation && approvalContractId !== null
              ? `Confirm approval-bound send ${approvalContractId}`
              : `Confirm ${confirmation.label}`,
          "data-ultradex-focus": "confirmation-primary",
        },
      });
      enforceMinimumInteractiveTarget(confirm);
      confirm.disabled =
        confirmation.stage === "submitting" ||
        confirmation.bindingError !== null ||
        !isMutationAvailable(this.store);
      confirm.addEventListener("click", () => {
        this.focusAfterRender = "confirmation-primary";
        if (
          isSecondOutreachConfirmation &&
          approvalContractId !== null
        ) {
          void controller.confirmOutreachSend(
            confirmation.id,
            approvalContractId,
          );
          return;
        }
        void controller.confirm(confirmation.id);
      });
      if (!isMutationAvailable(this.store)) {
        review.createEl("p", {
          text: "Projection state changed. Submission is unavailable; start a fresh review after a verified refresh.",
        });
      }
    }
    renderCommandForms(root, {
      disabled: !isMutationAvailable(this.store),
      drafts: this.commandDrafts,
      onDraftChange: (commandName, fieldName, value) => {
        const commandDraft =
          this.commandDrafts.get(commandName) ?? {};
        commandDraft[fieldName] = value;
        this.commandDrafts.set(commandName, commandDraft);
      },
      onPrepare: (command) => {
        this.focusAfterRender = "confirmation-primary";
        controller.prepare(command);
      },
    });
  }

  private renderMutationRecords(
    root: HTMLElement,
    controller: CommandController,
  ): void {
    const records = controller.getState().records;
    if (records.length === 0) {
      return;
    }
    const section = root.createEl("section", {
      cls: "ultradex-governed-outcomes",
      attr: {
        "aria-labelledby": "ultradex-outcomes-heading",
        "aria-live": "polite",
        "aria-atomic": "false",
      },
    });
    section.createEl("h3", {
      text: "Governed outcomes",
      attr: { id: "ultradex-outcomes-heading" },
    });
    for (const record of records) {
      this.renderMutationRecord(section, controller, record);
    }
  }

  private renderMutationRecord(
    section: HTMLElement,
    controller: CommandController,
    record: GovernedMutationRecord,
  ): void {
    const card = section.createEl("article", {
      cls: "ultradex-governed-card",
      attr: {
        "data-state": record.state,
        "data-evidence-status": record.evidenceStatus,
      },
    });
    const heading = card.createDiv({
      cls: "ultradex-governed-card__heading",
    });
    heading.createEl("h4", {
      text: sanitizeDisplayText(record.commandName),
    });
    renderContractState(heading, record.state);
    card.createEl("p", { text: record.consequence });

    const evidence = card.createDiv({
      cls: "ultradex-governed-card__evidence",
    });
    evidence.createEl("strong", { text: "Submitted" });
    evidence.createEl("span", {
      text: formatTimestamp(record.submittedAt),
    });
    evidence.createEl("strong", { text: "Evidence status" });
    evidence.createEl("span", {
      text: formatLabel(record.evidenceStatus),
    });
    evidence.createEl("strong", { text: "Idempotency key" });
    this.renderCopyableId(
      evidence,
      record.idempotencyKey,
      "idempotency",
    );
    evidence.createEl("strong", { text: "Correlation ID" });
    this.renderCopyableId(
      evidence,
      record.correlationId,
      "correlation",
    );
    evidence.createEl("strong", { text: "Operation ID" });
    if (record.operationId === null) {
      evidence.createEl("span", { text: "Not returned" });
    } else {
      this.renderCopyableId(
        evidence,
        record.operationId,
        "operation",
      );
    }
    if (record.serverReasonCode !== null) {
      card.createEl("p", {
        text: `Server reason code: ${sanitizeDisplayText(record.serverReasonCode)}`,
      });
    }
    if (record.serverReason !== null) {
      card.createEl("p", {
        text: `Server reason: ${sanitizeDisplayText(record.serverReason)}`,
      });
    }
    if (record.localReason !== null) {
      card.createEl("p", {
        cls: "ultradex-governed-card__notice",
        text: sanitizeDisplayText(record.localReason, "Unavailable", 260),
      });
    }
    if (record.completionUnknown) {
      card.createEl("strong", { text: "Completion unknown" });
      card.createEl("p", {
        text: "This attempt cannot be retried. Start a fresh form and confirmation only for a deliberately new command.",
      });
    }
    if (
      record.evidenceStatus !== "complete" &&
      record.operationId !== null
    ) {
      const refreshing = controller
        .getState()
        .refreshingRecordIds.includes(record.id);
      const refresh = card.createEl("button", {
        cls: "ultradex-button",
        text: refreshing
          ? "Refreshing evidence…"
          : "Refresh operation evidence",
        type: "button",
        attr: {
          "aria-label": `${refreshing ? "Refreshing" : "Refresh"} operation evidence ${sanitizeDisplayText(record.operationId, "Unavailable", 180)}`,
          "data-ultradex-focus": `record:${record.id}:refresh`,
        },
      });
      enforceMinimumInteractiveTarget(refresh);
      refresh.disabled = refreshing;
      refresh.addEventListener("click", () => {
        void controller.refreshRecord(record.id);
      });
    }
    if (record.events.length > 0) {
      const events = card.createEl("ul", {
        cls: "ultradex-lifecycle-events",
        attr: { "aria-label": "Lifecycle events" },
      });
      for (const event of record.events) {
        const item = events.createEl("li");
        item.createSpan({
          text: `${formatTimestamp(event.timestamp)} — ${sanitizeDisplayText(event.eventType)} — Event ID `,
        });
        this.renderCopyableId(item, String(event.id), "event");
      }
    }
    if (record.approval !== null) {
      const approval = card.createDiv({
        cls: "ultradex-approval-evidence",
      });
      approval.createEl("strong", { text: "Approval contract" });
      approval.createEl("code", { text: record.approval.approvalId });
      approval.createEl("strong", { text: "Outreach ID" });
      approval.createEl("code", { text: record.approval.outreachId });
      approval.createEl("strong", { text: "Message commitment" });
      approval.createEl("code", {
        text: record.approval.messageCommitment,
      });
      approval.createEl("strong", { text: "Channel" });
      approval.createEl("code", { text: record.approval.channel });
      approval.createEl("span", {
        text: sanitizeDisplayText(record.approval.status),
      });
    }
    if (record.receipt !== null) {
      const receipt = card.createEl("section", {
        cls: "ultradex-receipt",
        attr: { "aria-label": "Execution receipt evidence" },
      });
      receipt.createEl("h5", { text: "Execution receipt" });
      receipt.createEl("strong", { text: "Proof status" });
      receipt.createEl("code", { text: record.receipt.proofStatus });
      receipt.createEl("p", {
        text: "Local signature verification is unavailable. This receipt is server-recorded evidence only.",
      });
      receipt.createEl("strong", { text: "Receipt hash" });
      receipt.createEl("code", { text: record.receipt.receiptHash });
      receipt.createEl("strong", { text: "Signature key ID" });
      receipt.createEl("code", {
        text: record.receipt.payload.signature.key_id,
      });
      receipt.createEl("strong", { text: "Signed timestamp" });
      receipt.createEl("code", {
        text: record.receipt.payload.completed_at,
      });
      receipt.createEl("strong", { text: "Audit reference" });
      receipt.createEl("code", { text: record.receipt.receiptId });
      receipt.createEl("strong", { text: "Signed payload" });
      receipt.createEl("pre", {
        text: JSON.stringify(record.receipt.payload, null, 2),
      });
    }
  }

  private renderConnection(
    root: HTMLElement,
    state: ProjectionStoreState,
  ): void {
    const connection = root.createEl("section", {
      cls: "ultradex-connection",
      attr: {
        "aria-label": "Connection and snapshot state",
        "aria-live": "polite",
        "data-state": state.status,
      },
    });
    const connectionState =
      state.status === "ready"
        ? "Connected"
        : state.status === "stale"
          ? "Stale snapshot"
          : state.status === "refreshing"
            ? "Refreshing verified snapshot"
            : state.status === "loading"
              ? "Connecting"
              : "Unavailable";
    connection.createEl("strong", { text: connectionState });
    connection.createEl("span", {
      text: `Service ${configuredServiceOrigin(this.baseUrl)}`,
    });
    if (state.snapshot !== null) {
      connection.createEl("span", {
        text: `Verified ${formatTimestamp(state.snapshot.receivedAt)}`,
      });
    }
    if (state.errorCategory !== null) {
      connection.createEl("span", {
        text: errorStateCopy(state.errorCategory),
      });
    }
    const projectionFailure = failedProjectionCopy(state);
    if (projectionFailure !== null && state.snapshot !== null) {
      connection.createEl("span", { text: projectionFailure });
    }
    if (
      state.errorCategory === "schema" &&
      state.snapshot !== null
    ) {
      connection.createEl("span", {
        text: errorGuidance(state.errorCategory, true),
      });
    }
  }

  private renderUnavailable(
    root: HTMLElement,
    state: ProjectionStoreState,
  ): void {
    const unavailable = root.createEl("section", {
      cls: "ultradex-unavailable",
      attr: {
        "aria-labelledby": "ultradex-unavailable-heading",
      },
    });
    if (state.status === "loading") {
      unavailable.createEl("h3", {
        text: "Loading verified projections",
        attr: { id: "ultradex-unavailable-heading" },
      });
      unavailable.createEl("p", {
        text: "Waiting for a complete projection snapshot.",
      });
      return;
    }
    unavailable.createEl("h3", {
      text:
        failedProjectionCopy(state) ??
        errorStateCopy(state.errorCategory),
      attr: { id: "ultradex-unavailable-heading" },
    });
    unavailable.createEl("p", {
      text: errorGuidance(state.errorCategory, false),
    });
  }

  private renderFreshness(
    root: HTMLElement,
    snapshot: ProjectionSnapshot,
  ): void {
    const strip = root.createEl("section", {
      cls: "ultradex-freshness-strip",
      attr: { "aria-label": "Projection freshness" },
    });
    const entries = [
      ["Opportunities", snapshot.opportunities.freshness],
      ["Applications", snapshot.applications.freshness],
      ["Relationships", snapshot.relationships.freshness],
      ["Outreach", snapshot.outreach.freshness],
    ] as const;
    for (const [label, freshness] of entries) {
      const entry = strip.createDiv({
        cls: "ultradex-freshness-strip__entry",
      });
      entry.createSpan({ text: label });
      renderFreshnessBadge(entry, freshness);
    }
  }

  private renderOperations(
    root: HTMLElement,
    operations: readonly Operation[],
  ): void {
    const panel = createPanel(
      root,
      "ultradex-operations-heading",
      "Recent operations",
      operations.length,
    );
    panel.classList.add("ultradex-operations");
    if (operations.length === 0) {
      panel.createEl("p", {
        cls: "ultradex-empty-state",
        text: "No recent operations.",
      });
      return;
    }
    const body = createTable(panel, "Recent operations", [
      "State",
      "Command",
      "Operation ID",
      "Correlation ID",
      "Created",
    ]);
    for (const operation of operations) {
      const row = body.createEl("tr");
      const stateCell = row.createEl("th", { attr: { scope: "row" } });
      renderContractState(stateCell, operation.status);
      row.createEl("td", {
        text: sanitizeDisplayText(operation.command),
      });
      const operationCell = row.createEl("td");
      this.renderCopyableId(
        operationCell,
        operation.id,
        "operation",
      );
      const correlationCell = row.createEl("td");
      if (operation.correlationId === null) {
        correlationCell.setText("Not provided");
      } else {
        this.renderCopyableId(
          correlationCell,
          operation.correlationId,
          "correlation",
        );
      }
      row.createEl("td", {
        text: formatTimestamp(operation.createdAt),
      });
    }
  }

  private renderCopyableId(
    container: HTMLElement,
    value: string,
    kind: "operation" | "correlation" | "idempotency" | "event",
  ): void {
    const safeValue = sanitizeDisplayText(value, "Unavailable", 180);
    container.createEl("code", { text: safeValue });
    const label =
      kind === "operation"
        ? "operation ID"
        : kind === "correlation"
          ? "correlation ID"
          : kind === "event"
            ? "event ID"
            : "idempotency key";
    const button = container.createEl("button", {
      cls: "ultradex-copy-button",
      text: "Copy",
      type: "button",
      attr: {
        "aria-label": `Copy ${label} ${safeValue}`,
        "aria-live": "polite",
      },
    });
    enforceMinimumInteractiveTarget(button);
    button.addEventListener("click", () => {
      void this.copyText(value).then(
        () => {
          button.setText("Copied");
          button.setAttribute(
            "aria-label",
            `Copied ${label} ${safeValue}`,
          );
        },
        () => {
          button.setText("Copy failed");
          button.setAttribute(
            "aria-label",
            `Copy failed for ${label} ${safeValue}`,
          );
        },
      );
    });
  }

  private currentFocusKey(): string | null {
    const active = this.contentEl.ownerDocument.activeElement;
    if (
      active === null ||
      !this.contentEl.contains(active)
    ) {
      return null;
    }
    return (active as HTMLElement).getAttribute(
      "data-ultradex-focus",
    );
  }

  private restoreFocus(focusKey: string | null): void {
    if (focusKey === null) {
      return;
    }
    const candidates = this.contentEl.querySelectorAll<HTMLElement>(
      "[data-ultradex-focus]",
    );
    for (const candidate of Array.from(candidates)) {
      if (
        candidate.getAttribute("data-ultradex-focus") === focusKey
      ) {
        candidate.focus();
        return;
      }
    }
  }
}
