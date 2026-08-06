import type { JobSearchCommand } from "@ultradex/sdk";
import { describe, expect, test } from "vitest";

import { renderCommandForms } from "../src/mutations/command-forms.js";
import { TestElement } from "./obsidian-runtime.js";

function descendants(
  element: TestElement,
  predicate: (candidate: TestElement) => boolean,
): TestElement[] {
  return [
    ...(predicate(element) ? [element] : []),
    ...element.children.flatMap((child) => descendants(child, predicate)),
  ];
}

function byAttribute(
  element: TestElement,
  name: string,
  value: string,
): TestElement {
  const match = descendants(
    element,
    (candidate) => candidate.getAttribute(name) === value,
  )[0];
  if (match === undefined) {
    throw new Error(`Synthetic DOM element ${name}=${value} not found`);
  }
  return match;
}

async function submitForm(
  root: TestElement,
  commandName: string,
  values: Readonly<Record<string, string>>,
): Promise<void> {
  const form = byAttribute(root, "data-command", commandName);
  for (const [name, value] of Object.entries(values)) {
    byAttribute(form, "name", name).value = value;
  }
  await form.eventListeners.submit?.[0]?.({
    preventDefault(): void {},
  });
}

describe("renderCommandForms", () => {
  test("maps every one of the nine rendered native forms to the exact typed command fields", async () => {
    const root = new TestElement();
    const prepared: JobSearchCommand[] = [];
    const commitment =
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    renderCommandForms(root as unknown as HTMLElement, {
      disabled: false,
      onPrepare: (command) => prepared.push(command),
    });
    const examples = [
      [
        "sources.ingest",
        {
          sourceKind: "manual",
          sourceRef: "source-synthetic-001",
          observedAt: "2026-07-29T17:10:00Z",
        },
        {
          commandName: "sources.ingest",
          parameters: {
            sourceKind: "manual",
            sourceRef: "source-synthetic-001",
            observedAt: "2026-07-29T17:10:00Z",
          },
        },
      ],
      [
        "opportunities.create",
        {
          employer: "Synthetic Systems",
          title: "Platform Engineer",
          sourceEvidenceId: "evidence-synthetic-001",
        },
        {
          commandName: "opportunities.create",
          parameters: {
            employer: "Synthetic Systems",
            title: "Platform Engineer",
            sourceEvidenceId: "evidence-synthetic-001",
          },
        },
      ],
      [
        "opportunities.score",
        {
          opportunityId: "opportunity-synthetic-001",
          lens: "executive",
        },
        {
          commandName: "opportunities.score",
          parameters: {
            opportunityId: "opportunity-synthetic-001",
            lens: "executive",
          },
        },
      ],
      [
        "applications.transition",
        {
          applicationId: "application-synthetic-001",
          status: "interviewing",
          occurredAt: "2026-07-29T17:11:00+00:00",
        },
        {
          commandName: "applications.transition",
          parameters: {
            applicationId: "application-synthetic-001",
            status: "interviewing",
            occurredAt: "2026-07-29T17:11:00+00:00",
          },
        },
      ],
      [
        "relationships.sync",
        {
          opportunityId: "opportunity-synthetic-001",
          dexContactRef: "dex-synthetic-001",
        },
        {
          commandName: "relationships.sync",
          parameters: {
            opportunityId: "opportunity-synthetic-001",
            dexContactRef: "dex-synthetic-001",
          },
        },
      ],
      [
        "outreach.prepare",
        {
          opportunityId: "opportunity-synthetic-001",
          channel: "linkedin",
          messageCommitment: commitment,
          relationshipId: "relationship-synthetic-001",
        },
        {
          commandName: "outreach.prepare",
          parameters: {
            opportunityId: "opportunity-synthetic-001",
            channel: "linkedin",
            messageCommitment: commitment,
            relationshipId: "relationship-synthetic-001",
          },
        },
      ],
      [
        "outreach.approve",
        {
          outreachId: "outreach-synthetic-001",
          messageCommitment: commitment,
        },
        {
          commandName: "outreach.approve",
          parameters: {
            outreachId: "outreach-synthetic-001",
            messageCommitment: commitment,
          },
        },
      ],
      [
        "outreach.send",
        {
          outreachId: "outreach-synthetic-001",
          approvalContractId: "approval-synthetic-001",
          messageCommitment: commitment,
          channel: "linkedin",
        },
        {
          commandName: "outreach.send",
          parameters: {
            outreachId: "outreach-synthetic-001",
            approvalContractId: "approval-synthetic-001",
            messageCommitment: commitment,
            channel: "linkedin",
          },
        },
      ],
      [
        "evidence.export",
        {
          subjectType: "opportunity",
          subjectId: "opportunity-synthetic-001",
        },
        {
          commandName: "evidence.export",
          parameters: {
            subjectType: "opportunity",
            subjectId: "opportunity-synthetic-001",
            profile: "accountability.v1",
          },
        },
      ],
    ] as const;

    for (const [commandName, values, expected] of examples) {
      await submitForm(root, commandName, values);
      expect(prepared.at(-1)).toEqual(expected);
    }
    expect(prepared).toHaveLength(9);
  });

  test("rejects timestamps without an RFC3339 timezone and reports the field-specific correction", async () => {
    const root = new TestElement();
    const prepared: JobSearchCommand[] = [];
    renderCommandForms(root as unknown as HTMLElement, {
      disabled: false,
      onPrepare: (command) => prepared.push(command),
    });

    await submitForm(root, "sources.ingest", {
      sourceKind: "manual",
      sourceRef: "source-synthetic-001",
      observedAt: "2026-07-29T17:10",
    });

    expect(prepared).toEqual([]);
    expect(
      byAttribute(
        root,
        "data-command",
        "sources.ingest",
      ).textContent,
    ).toContain(
      "Observed at must be an RFC3339 timestamp with Z or a numeric timezone.",
    );
  });

  test("rejects malformed message commitments with an actionable sha256 requirement", async () => {
    const root = new TestElement();
    const prepared: JobSearchCommand[] = [];
    renderCommandForms(root as unknown as HTMLElement, {
      disabled: false,
      onPrepare: (command) => prepared.push(command),
    });

    await submitForm(root, "outreach.send", {
      outreachId: "outreach-synthetic-001",
      approvalContractId: "approval-synthetic-001",
      messageCommitment: "sha256:not-a-digest",
      channel: "linkedin",
    });

    expect(prepared).toEqual([]);
    expect(
      byAttribute(root, "data-command", "outreach.send").textContent,
    ).toContain(
      "Message commitment must be sha256: followed by exactly 64 lowercase hexadecimal characters.",
    );
  });
});
