import { describe, expect, it } from "vitest";
import type { DailyAvailability, OutboxMessage, RecruiterPillReply } from "@ultradex/sdk";

import {
  applyRecruiterPillToComposer,
  filterMessages,
  formatAvailabilitySlotsForEmail,
  inboxEmptyState,
  messageChannelTone,
  messageStatusTone,
} from "./inbox.js";

const sampleMessages: OutboxMessage[] = [
  {
    id: "msg-1",
    channel: "gmail",
    direction: "inbound",
    recipientAddress: "recruiter@anthropic.com",
    recipientName: "Jessica Wong",
    recipientId: "dex:contact-jw",
    subject: "Exciting leadership opportunity at Anthropic (Head of AI Architecture)",
    bodyText: "Hi Nate, came across your work on sovereign multi-agent systems and wanted to connect about our Head of AI role.",
    bodyHtml: null,
    threadId: "thread-1",
    inReplyTo: null,
    references: null,
    status: "pending_approval",
    messageCommitment: "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    approvalId: "approval-1",
    sentEvidenceRef: null,
    externalMessageId: "gmail-ext-1",
    errorMessage: null,
    createdAt: "2026-08-23T14:00:00Z",
    sentAt: null,
  },
  {
    id: "msg-2",
    channel: "linkedin",
    direction: "outbound",
    recipientAddress: "alex@deepgram.com",
    recipientName: "Alex Miller",
    recipientId: "dex:contact-2",
    subject: "Re: VP Voice AI Role - Availability",
    bodyText: "Hi Alex, great connecting. Here is my availability for a 30-min call:\n• Tuesday, Aug 25: 10:00 AM CT, 2:00 PM CT\nLooking forward to speaking.",
    bodyHtml: null,
    threadId: "thread-2",
    inReplyTo: null,
    references: null,
    status: "sent",
    messageCommitment: "",
    approvalId: null,
    sentEvidenceRef: "evidence:sent-2",
    externalMessageId: "li-msg-2",
    errorMessage: null,
    createdAt: "2026-08-22T09:00:00Z",
    sentAt: "2026-08-22T09:05:00Z",
  },
];

const sampleAvailability: DailyAvailability[] = [
  {
    dateStr: "2026-08-25",
    dayName: "Tuesday",
    slots30min: [
      {
        start: "2026-08-25T15:00:00Z",
        end: "2026-08-25T15:30:00Z",
        durationMinutes: 30,
        dayKey: "2026-08-25",
        formattedCt: "Tue Aug 25 · 10:00 AM - 10:30 AM CT",
      },
      {
        start: "2026-08-25T19:00:00Z",
        end: "2026-08-25T19:30:00Z",
        durationMinutes: 30,
        dayKey: "2026-08-25",
        formattedCt: "Tue Aug 25 · 02:00 PM - 02:30 PM CT",
      },
    ],
    slots45min: [],
  },
  {
    dateStr: "2026-08-26",
    dayName: "Wednesday",
    slots30min: [
      {
        start: "2026-08-26T18:00:00Z",
        end: "2026-08-26T18:30:00Z",
        durationMinutes: 30,
        dayKey: "2026-08-26",
        formattedCt: "Wed Aug 26 · 01:00 PM - 01:30 PM CT",
      },
    ],
    slots45min: [],
  },
];

describe("inbox helper module", () => {
  it("formats channel and status tones appropriately", () => {
    expect(messageChannelTone("gmail")).toBe("accent");
    expect(messageChannelTone("linkedin")).toBe("warning");
    expect(messageChannelTone("dex")).toBe("neutral");

    expect(messageStatusTone("sent")).toBe("success");
    expect(messageStatusTone("approved")).toBe("accent");
    expect(messageStatusTone("pending_approval")).toBe("warning");
    expect(messageStatusTone("failed")).toBe("danger");
  });

  it("formats Google Calendar availability slots for email injection", () => {
    const formatted = formatAvailabilitySlotsForEmail(sampleAvailability);
    expect(formatted).toContain("Tuesday, 2026-08-25: 10:00 AM - 10:30 AM CT, 02:00 PM - 02:30 PM CT");
    expect(formatted).toContain("Wednesday, 2026-08-26: 01:00 PM - 01:30 PM CT");
  });

  it("provides fallback template when availability array is empty", () => {
    const fallback = formatAvailabilitySlotsForEmail([]);
    expect(fallback).toContain("Tuesday & Thursday 10:00 AM – 2:00 PM CT");
  });

  it("applies recruiter pill reply to composer inputs", () => {
    const pill: RecruiterPillReply = {
      pillType: "accept_and_schedule",
      label: "Accept & Share Slots",
      subject: "Re: Anthropic Head of AI Architecture",
      bodyText: "Thanks for reaching out! I'd love to chat. Here is my current availability:\n• Tuesday 10:00 AM CT\nBest,\nNate",
      bodyHtml: null,
      calendarSlotsInjected: ["2026-08-25T15:00:00Z"],
      requiresApproval: false,
      contextSummary: "Accepts recruiter request with live GCal slots.",
    };

    const composer = applyRecruiterPillToComposer(pill, "recruiter@anthropic.com", "Jessica Wong");
    expect(composer.recipientAddress).toBe("recruiter@anthropic.com");
    expect(composer.recipientName).toBe("Jessica Wong");
    expect(composer.subject).toBe(pill.subject);
    expect(composer.bodyText).toBe(pill.bodyText);
    expect(composer.channel).toBe("gmail");
  });

  it("filters messages by channel, status, and search query", () => {
    const gmailOnly = filterMessages(sampleMessages, { channel: "gmail" });
    expect(gmailOnly).toHaveLength(1);
    expect(gmailOnly[0]?.id).toBe("msg-1");

    const sentOnly = filterMessages(sampleMessages, { status: "sent" });
    expect(sentOnly).toHaveLength(1);
    expect(sentOnly[0]?.id).toBe("msg-2");

    const searchAnthropic = filterMessages(sampleMessages, { search: "Anthropic" });
    expect(searchAnthropic).toHaveLength(1);
    expect(searchAnthropic[0]?.id).toBe("msg-1");
  });

  it("generates correct empty states for filtered and non-filtered states", () => {
    expect(inboxEmptyState({}).title).toBe("Inbox is clean");
    expect(inboxEmptyState({ channel: "linkedin" }).title).toBe("No messages match filters");
  });
});
