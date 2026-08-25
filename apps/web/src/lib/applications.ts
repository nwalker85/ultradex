import type { Application, ApplicationStage, ApplicationStatus } from "@ultradex/sdk";

export const APPLICATION_STATUS_STEPS = [
  "draft",
  "applied",
  "screening",
  "interviewing",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
  "closed",
] as const;

export type ApplicationStatusFilter = "" | (typeof APPLICATION_STATUS_STEPS)[number];

export type DeadlineClassification = "overdue" | "due-today" | "upcoming" | "none";

export interface DeadlineInfo {
  readonly kind: DeadlineClassification;
  readonly label: string;
  readonly daysDiff: number | null;
}

export function classifyApplicationDeadline(
  deadline: string | null | undefined,
  now = new Date(),
): DeadlineInfo {
  if (!deadline) {
    return { kind: "none", label: "No deadline set", daysDiff: null };
  }

  const deadlineMs = Date.parse(deadline);
  if (Number.isNaN(deadlineMs)) {
    return { kind: "none", label: "Invalid date", daysDiff: null };
  }

  // Compare on date boundary (UTC/local day diff)
  const nowDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(deadlineMs);
  const targetDate = new Date(target.getFullYear(), target.getMonth(), target.getDate());

  const msPerDay = 1000 * 60 * 60 * 24;
  const daysDiff = Math.round((targetDate.getTime() - nowDate.getTime()) / msPerDay);

  if (daysDiff < 0) {
    return {
      kind: "overdue",
      label: `Overdue by ${Math.abs(daysDiff)}d`,
      daysDiff,
    };
  }
  if (daysDiff === 0) {
    return {
      kind: "due-today",
      label: "Due today",
      daysDiff: 0,
    };
  }
  return {
    kind: "upcoming",
    label: `Due in ${daysDiff}d`,
    daysDiff,
  };
}

export interface FormattedStageStep {
  readonly status: string;
  readonly label: string;
  readonly occurredAt: string | null;
  readonly evidenceRef: string | null;
  readonly isCurrent: boolean;
  readonly isPast: boolean;
}

export const PRIMARY_STAGES = ["applied", "screening", "interviewing", "offer"] as const;

export function formatStageProgression(
  currentStatus: ApplicationStatus,
  stageHistory: readonly ApplicationStage[],
): FormattedStageStep[] {
  const historyMap = new Map<string, ApplicationStage>();
  for (const h of stageHistory) {
    historyMap.set(h.status, h);
  }

  const currentIndex = PRIMARY_STAGES.indexOf(currentStatus as (typeof PRIMARY_STAGES)[number]);

  return PRIMARY_STAGES.map((stage, idx) => {
    const record = historyMap.get(stage);
    const isCurrent = stage === currentStatus;
    const isPast = currentIndex >= 0 ? idx < currentIndex : Boolean(record);

    return {
      status: stage,
      label: stage.charAt(0).toUpperCase() + stage.slice(1),
      occurredAt: record?.occurredAt ?? null,
      evidenceRef: record?.evidenceRef ?? null,
      isCurrent,
      isPast,
    };
  });
}

export function applicationsEmptyState(filter: ApplicationStatusFilter): {
  title: string;
  description: string;
} {
  if (filter === "") {
    return {
      title: "No applications found",
      description: "Convert a high-fit lead to an opportunity or originate an application record.",
    };
  }
  return {
    title: `No applications in stage "${filter}"`,
    description: `No active applications currently match stage "${filter}". Reset filter to view all applications.`,
  };
}

export function filterApplications(
  applications: readonly Application[],
  filter: ApplicationStatusFilter,
): Application[] {
  if (!filter) return [...applications];
  return applications.filter((app) => app.status === filter);
}

export function findApplicationById(
  applications: readonly Application[],
  id: string,
): Application | null {
  return applications.find((a) => a.applicationId === id) ?? null;
}
