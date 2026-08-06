import type { OperationStatus } from "@ultradex/sdk";

import type { GovernedOutcomeState } from "../mutations/operation-tracker.js";

type VisibleContractState = OperationStatus | GovernedOutcomeState;

const OPERATION_STATUS_LABELS: Readonly<
  Record<VisibleContractState, string>
> = {
  accepted: "Accepted",
  "approval-required": "Approval required",
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  refused: "Refused",
  succeeded: "Succeeded",
  unverifiable: "Unverifiable",
};

export function renderContractState(
  container: HTMLElement,
  status: VisibleContractState,
): HTMLSpanElement {
  return container.createSpan({
    cls: "ultradex-contract-state",
    text: OPERATION_STATUS_LABELS[status],
    attr: {
      "data-state": status,
    },
  });
}
