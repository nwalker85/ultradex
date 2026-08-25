import { describe, expect, it } from "vitest";
import type { Application } from "@ultradex/sdk";

import {
  applicationsEmptyState,
  classifyApplicationDeadline,
  filterApplications,
  findApplicationById,
  formatStageProgression,
} from "./applications.js";

const sampleApplications: Application[] = [
  {
    applicationId: "app-1",
    opportunityId: "opp-1",
    status: "interviewing",
    stageHistory: [
      {
        status: "applied",
        occurredAt: "2026-08-01T10:00:00Z",
        evidenceRef: "evidence:app-1-applied",
      },
      {
        status: "screening",
        occurredAt: "2026-08-05T14:00:00Z",
        evidenceRef: "evidence:app-1-screen",
      },
      {
        status: "interviewing",
        occurredAt: "2026-08-12T16:00:00Z",
        evidenceRef: "evidence:app-1-interview",
      },
    ],
    artifactRefs: ["doc:resume-v4", "doc:cover-letter"],
    nextAction: "Executive presentation with VP of Engineering",
    nextActionAt: "2026-08-25T15:00:00Z",
    freshness: null,
    createdAt: "2026-08-01T10:00:00Z",
    updatedAt: "2026-08-12T16:00:00Z",
  },
  {
    applicationId: "app-2",
    opportunityId: "opp-2",
    status: "applied",
    stageHistory: [
      {
        status: "applied",
        occurredAt: "2026-08-20T10:00:00Z",
        evidenceRef: null,
      },
    ],
    artifactRefs: [],
    nextAction: "Await recruiter review",
    nextActionAt: "2026-08-20T10:00:00Z", // overdue relative to 2026-08-24
    freshness: null,
    createdAt: "2026-08-20T10:00:00Z",
    updatedAt: "2026-08-20T10:00:00Z",
  },
];

describe("applications helper module", () => {
  const referenceNow = new Date("2026-08-24T12:00:00Z");

  it("classifies application deadlines accurately", () => {
    // Overdue
    const overdue = classifyApplicationDeadline("2026-08-20T10:00:00Z", referenceNow);
    expect(overdue.kind).toBe("overdue");
    expect(overdue.daysDiff).toBe(-4);
    expect(overdue.label).toBe("Overdue by 4d");

    // Due today
    const dueToday = classifyApplicationDeadline("2026-08-24T18:00:00Z", referenceNow);
    expect(dueToday.kind).toBe("due-today");
    expect(dueToday.daysDiff).toBe(0);
    expect(dueToday.label).toBe("Due today");

    // Upcoming
    const upcoming = classifyApplicationDeadline("2026-08-27T10:00:00Z", referenceNow);
    expect(upcoming.kind).toBe("upcoming");
    expect(upcoming.daysDiff).toBe(3);
    expect(upcoming.label).toBe("Due in 3d");

    // No deadline / invalid
    expect(classifyApplicationDeadline(null, referenceNow).kind).toBe("none");
    expect(classifyApplicationDeadline("invalid-date", referenceNow).kind).toBe("none");
  });

  it("formats stage progression timeline accurately", () => {
    const app = sampleApplications[0]!;
    const steps = formatStageProgression(app.status, app.stageHistory);

    expect(steps).toHaveLength(4); // applied, screening, interviewing, offer
    expect(steps[0]?.status).toBe("applied");
    expect(steps[0]?.isPast).toBe(true);
    expect(steps[0]?.isCurrent).toBe(false);

    expect(steps[1]?.status).toBe("screening");
    expect(steps[1]?.isPast).toBe(true);

    expect(steps[2]?.status).toBe("interviewing");
    expect(steps[2]?.isCurrent).toBe(true);
    expect(steps[2]?.isPast).toBe(false);

    expect(steps[3]?.status).toBe("offer");
    expect(steps[3]?.isCurrent).toBe(false);
    expect(steps[3]?.isPast).toBe(false);
  });

  it("generates clear empty states", () => {
    const emptyAll = applicationsEmptyState("");
    expect(emptyAll.title).toBe("No applications found");

    const emptyOffer = applicationsEmptyState("offer");
    expect(emptyOffer.title).toBe('No applications in stage "offer"');
  });

  it("filters applications by status", () => {
    const interviewing = filterApplications(sampleApplications, "interviewing");
    expect(interviewing).toHaveLength(1);
    expect(interviewing[0]?.applicationId).toBe("app-1");

    const none = filterApplications(sampleApplications, "offer");
    expect(none).toHaveLength(0);
  });

  it("finds application by ID", () => {
    expect(findApplicationById(sampleApplications, "app-1")?.opportunityId).toBe("opp-1");
    expect(findApplicationById(sampleApplications, "missing")).toBeNull();
  });
});
