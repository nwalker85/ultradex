import type {
  ApplicationTransitionParameters,
  EvidenceExportParameters,
  JobSearchCommand,
  JobSearchCommandName,
  OpportunityCreateParameters,
  OpportunityScoreParameters,
  OutreachApproveParameters,
  OutreachPrepareParameters,
  OutreachSendParameters,
  RelationshipSyncParameters,
  SourcesIngestParameters,
} from "@ultradex/sdk";

export interface RenderCommandFormsOptions {
  readonly disabled: boolean;
  readonly drafts?: CommandFormDrafts;
  readonly onDraftChange?: (
    commandName: JobSearchCommandName,
    fieldName: string,
    value: string,
  ) => void;
  readonly onPrepare: (command: JobSearchCommand) => void;
}

export type CommandFormDrafts = ReadonlyMap<
  JobSearchCommandName,
  Readonly<Record<string, string>>
>;

interface CommandField {
  readonly name: string;
  readonly label: string;
  readonly type?: "text" | "datetime-local";
  readonly options?: readonly string[];
  readonly optional?: boolean;
  readonly fixedValue?: string;
}

export interface TypedCommandForm<
  Name extends JobSearchCommandName,
  Parameters,
> {
  readonly commandName: Name;
  readonly label: string;
  readonly consequence: string;
  create(parameters: Parameters): TypedCommandDraft<Name, Parameters>;
}

export interface TypedCommandDraft<
  Name extends JobSearchCommandName,
  Parameters,
> {
  readonly commandName: Name;
  readonly parameters: Parameters;
}

function defineForm<
  Name extends JobSearchCommandName,
  Parameters,
>(
  commandName: Name,
  label: string,
  consequence: string,
): TypedCommandForm<Name, Parameters> {
  return {
    commandName,
    label,
    consequence,
    create: (parameters) => ({ commandName, parameters }),
  };
}

export const COMMAND_FORMS = {
  sourcesIngest: defineForm<"sources.ingest", SourcesIngestParameters>(
    "sources.ingest",
    "Ingest source evidence",
    "Ask Ultradex to ingest one opaque source reference.",
  ),
  opportunityCreate: defineForm<
    "opportunities.create",
    OpportunityCreateParameters
  >(
    "opportunities.create",
    "Create opportunity",
    "Create a new opportunity record in Ultradex.",
  ),
  opportunityScore: defineForm<
    "opportunities.score",
    OpportunityScoreParameters
  >(
    "opportunities.score",
    "Score opportunity",
    "Recalculate one opportunity through the selected scoring lens.",
  ),
  applicationTransition: defineForm<
    "applications.transition",
    ApplicationTransitionParameters
  >(
    "applications.transition",
    "Transition application",
    "Change one application's governed lifecycle state.",
  ),
  relationshipSync: defineForm<
    "relationships.sync",
    RelationshipSyncParameters
  >(
    "relationships.sync",
    "Sync relationship",
    "Bind one opaque Dex contact reference to an opportunity.",
  ),
  outreachPrepare: defineForm<
    "outreach.prepare",
    OutreachPrepareParameters
  >(
    "outreach.prepare",
    "Prepare outreach",
    "Prepare approval-bound outreach from a message commitment only.",
  ),
  outreachApprove: defineForm<
    "outreach.approve",
    OutreachApproveParameters
  >(
    "outreach.approve",
    "Approve outreach",
    "Create an approval contract bound to this outreach and commitment.",
  ),
  outreachSend: defineForm<"outreach.send", OutreachSendParameters>(
    "outreach.send",
    "Send outreach",
    "Request delivery under the exact approval contract, commitment, and channel.",
  ),
  evidenceExport: defineForm<
    "evidence.export",
    EvidenceExportParameters
  >(
    "evidence.export",
    "Export evidence",
    "Create an accountability evidence export for one subject.",
  ),
} as const;

const FORM_FIELDS: Readonly<
  Record<JobSearchCommandName, readonly CommandField[]>
> = {
  "sources.ingest": [
    {
      name: "sourceKind",
      label: "Source kind",
      options: ["manual", "gmail", "linkedin", "dex", "web"],
    },
    { name: "sourceRef", label: "Opaque source reference" },
    {
      name: "observedAt",
      label: "Observed at (RFC 3339)",
    },
  ],
  "opportunities.create": [
    { name: "employer", label: "Employer" },
    { name: "title", label: "Role title" },
    { name: "sourceEvidenceId", label: "Source evidence ID" },
  ],
  "opportunities.score": [
    { name: "opportunityId", label: "Opportunity ID" },
    { name: "lens", label: "Scoring lens" },
  ],
  "applications.transition": [
    { name: "applicationId", label: "Application ID" },
    {
      name: "status",
      label: "New state",
      options: [
        "draft",
        "applied",
        "screening",
        "interviewing",
        "offer",
        "accepted",
        "rejected",
        "withdrawn",
        "closed",
      ],
    },
    { name: "occurredAt", label: "Occurred at (RFC 3339)" },
  ],
  "relationships.sync": [
    { name: "opportunityId", label: "Opportunity ID" },
    { name: "dexContactRef", label: "Opaque Dex contact reference" },
  ],
  "outreach.prepare": [
    { name: "opportunityId", label: "Opportunity ID" },
    {
      name: "channel",
      label: "Channel",
      options: ["gmail", "linkedin", "manual"],
    },
    { name: "messageCommitment", label: "Message commitment" },
    {
      name: "relationshipId",
      label: "Relationship ID",
      optional: true,
    },
  ],
  "outreach.approve": [
    { name: "outreachId", label: "Outreach ID" },
    { name: "messageCommitment", label: "Message commitment" },
  ],
  "outreach.send": [
    { name: "outreachId", label: "Outreach ID" },
    { name: "approvalContractId", label: "Approval contract ID" },
    { name: "messageCommitment", label: "Message commitment" },
    {
      name: "channel",
      label: "Channel",
      options: ["gmail", "linkedin", "manual"],
    },
  ],
  "evidence.export": [
    { name: "subjectType", label: "Subject type" },
    { name: "subjectId", label: "Subject ID" },
    {
      name: "profile",
      label: "Export profile",
      fixedValue: "accountability.v1",
    },
  ],
};

type FormMetadata = {
  readonly commandName: JobSearchCommandName;
  readonly label: string;
  readonly consequence: string;
};

export function commandFormMetadata(
  commandName: JobSearchCommandName,
): FormMetadata {
  const form = Object.values(COMMAND_FORMS).find(
    (candidate) => candidate.commandName === commandName,
  );
  if (form === undefined) {
    throw new Error("Unknown command form");
  }
  return form;
}

function requireValue(
  values: Readonly<Record<string, string>>,
  name: string,
): string {
  const value = values[name]?.trim() ?? "";
  if (value.length === 0) {
    throw new Error("A required command field is empty");
  }
  return value;
}

class CommandFormValidationError extends Error {}

export class CommandReviewError extends Error {}

function requireRfc3339Timestamp(
  values: Readonly<Record<string, string>>,
  name: string,
  label: string,
): string {
  const value = requireValue(values, name);
  if (
    !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/u.test(value) ||
    Number.isNaN(Date.parse(value))
  ) {
    throw new CommandFormValidationError(
      `${label} must be an RFC3339 timestamp with Z or a numeric timezone.`,
    );
  }
  return value;
}

function requireSha256Commitment(
  values: Readonly<Record<string, string>>,
): string {
  const value = requireValue(values, "messageCommitment");
  if (!/^sha256:[0-9a-f]{64}$/u.test(value)) {
    throw new CommandFormValidationError(
      "Message commitment must be sha256: followed by exactly 64 lowercase hexadecimal characters.",
    );
  }
  return value;
}

function commandFromValues(
  commandName: JobSearchCommandName,
  values: Readonly<Record<string, string>>,
): JobSearchCommand {
  switch (commandName) {
    case "sources.ingest":
      return COMMAND_FORMS.sourcesIngest.create({
        sourceKind: requireValue(values, "sourceKind") as
          | "gmail"
          | "linkedin"
          | "dex"
          | "manual"
          | "web",
        sourceRef: requireValue(values, "sourceRef"),
        observedAt: requireRfc3339Timestamp(
          values,
          "observedAt",
          "Observed at",
        ),
      });
    case "opportunities.create":
      return COMMAND_FORMS.opportunityCreate.create({
        employer: requireValue(values, "employer"),
        title: requireValue(values, "title"),
        sourceEvidenceId: requireValue(values, "sourceEvidenceId"),
      });
    case "opportunities.score":
      return COMMAND_FORMS.opportunityScore.create({
        opportunityId: requireValue(values, "opportunityId"),
        lens: requireValue(values, "lens"),
      });
    case "applications.transition":
      return COMMAND_FORMS.applicationTransition.create({
        applicationId: requireValue(values, "applicationId"),
        status: requireValue(values, "status") as
          ApplicationTransitionParameters["status"],
        occurredAt: requireRfc3339Timestamp(
          values,
          "occurredAt",
          "Occurred at",
        ),
      });
    case "relationships.sync":
      return COMMAND_FORMS.relationshipSync.create({
        opportunityId: requireValue(values, "opportunityId"),
        dexContactRef: requireValue(values, "dexContactRef"),
      });
    case "outreach.prepare": {
      const relationshipId = values.relationshipId?.trim() ?? "";
      return COMMAND_FORMS.outreachPrepare.create({
        opportunityId: requireValue(values, "opportunityId"),
        channel: requireValue(values, "channel") as
          OutreachPrepareParameters["channel"],
        messageCommitment: requireSha256Commitment(values),
        ...(relationshipId.length === 0 ? {} : { relationshipId }),
      });
    }
    case "outreach.approve":
      return COMMAND_FORMS.outreachApprove.create({
        outreachId: requireValue(values, "outreachId"),
        messageCommitment: requireSha256Commitment(values),
      });
    case "outreach.send":
      return COMMAND_FORMS.outreachSend.create({
        outreachId: requireValue(values, "outreachId"),
        approvalContractId: requireValue(values, "approvalContractId"),
        messageCommitment: requireSha256Commitment(values),
        channel: requireValue(values, "channel") as
          OutreachSendParameters["channel"],
      });
    case "evidence.export":
      return COMMAND_FORMS.evidenceExport.create({
        subjectType: requireValue(values, "subjectType"),
        subjectId: requireValue(values, "subjectId"),
        profile: "accountability.v1",
      });
  }
}

function createControl(
  label: HTMLElement,
  field: CommandField,
  commandName: JobSearchCommandName,
  disabled: boolean,
  draftValue: string | undefined,
): HTMLInputElement | HTMLSelectElement {
  let control: HTMLInputElement | HTMLSelectElement;
  if (field.options === undefined) {
    control = label.createEl("input", {
      type: field.type ?? "text",
      attr: {
        name: field.name,
        autocomplete: "off",
        "data-ultradex-focus": `form:${commandName}:${field.name}`,
      },
    });
    control.value = field.fixedValue ?? draftValue ?? "";
    if (field.fixedValue !== undefined) {
      control.readOnly = true;
    }
  } else {
    control = label.createEl("select", {
      attr: {
        name: field.name,
        "data-ultradex-focus": `form:${commandName}:${field.name}`,
      },
    });
    for (const option of field.options) {
      control.createEl("option", {
        text: option,
        attr: { value: option },
      });
    }
    control.value =
      draftValue !== undefined && field.options.includes(draftValue)
        ? draftValue
        : field.options[0] ?? "";
  }
  control.disabled = disabled;
  control.required = field.optional !== true;
  return control;
}

export function renderCommandForms(
  container: HTMLElement,
  options: RenderCommandFormsOptions,
): void {
  const section = container.createEl("section", {
    cls: "ultradex-command-bar",
    attr: { "aria-labelledby": "ultradex-command-heading" },
  });
  section.createEl("h3", {
    text: "Governed commands",
    attr: { id: "ultradex-command-heading" },
  });
  if (options.disabled) {
    section.createEl("p", {
      cls: "ultradex-command-bar__availability",
      text: "Commands are read-only until projections are authenticated, online, complete, and fresh.",
    });
  }
  const grid = section.createDiv({ cls: "ultradex-command-grid" });
  for (const formDefinition of Object.values(COMMAND_FORMS)) {
    const form = grid.createEl("form", {
      cls: "ultradex-command-form",
      attr: { "data-command": formDefinition.commandName },
    });
    form.createEl("h4", { text: formDefinition.label });
    const controls: Record<
      string,
      HTMLInputElement | HTMLSelectElement
    > = {};
    for (const field of FORM_FIELDS[formDefinition.commandName]) {
      const label = form.createEl("label");
      label.createSpan({ text: field.label });
      controls[field.name] = createControl(
        label,
        field,
        formDefinition.commandName,
        options.disabled,
        options.drafts
          ?.get(formDefinition.commandName)
          ?.[field.name],
      );
      controls[field.name].addEventListener("input", () => {
        options.onDraftChange?.(
          formDefinition.commandName,
          field.name,
          controls[field.name]?.value ?? "",
        );
      });
    }
    const error = form.createEl("p", {
      cls: "ultradex-command-form__error",
      attr: { "aria-live": "polite" },
    });
    const review = form.createEl("button", {
      cls: "ultradex-button",
      text: "Review",
      type: "submit",
      attr: {
        "aria-label": `Review ${formDefinition.label}`,
        "data-ultradex-focus": `form:${formDefinition.commandName}:review`,
      },
    });
    review.disabled = options.disabled;
    review.style.minHeight = "44px";
    review.style.minWidth = "44px";
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (options.disabled) {
        return;
      }
      const values = Object.fromEntries(
        Object.entries(controls).map(([name, control]) => [
          name,
          control.value,
        ]),
      );
      try {
        options.onPrepare(
          commandFromValues(formDefinition.commandName, values),
        );
      } catch (caught) {
        error.setText(
          caught instanceof CommandFormValidationError ||
            caught instanceof CommandReviewError
            ? caught.message
            : "Complete every required field with a valid contract value.",
        );
      }
    });
  }
}
