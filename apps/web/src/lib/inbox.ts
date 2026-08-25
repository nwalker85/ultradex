import type {
  ComposeMessageInput,
  DailyAvailability,
  MessageChannel,
  MessageStatus,
  OutboxMessage,
  RecruiterPillReply,
} from "@ultradex/sdk";

export interface MessageFilterCriteria {
  readonly channel?: string;
  readonly status?: string;
  readonly search?: string;
}

export function messageChannelTone(
  channel: MessageChannel | string | null | undefined,
): "accent" | "warning" | "neutral" {
  if (!channel) return "neutral";
  const c = channel.toLowerCase();
  if (c === "gmail") return "accent";
  if (c === "linkedin") return "warning";
  if (c === "dex") return "neutral";
  return "neutral";
}

export function messageStatusTone(
  status: MessageStatus | string | null | undefined,
): "success" | "warning" | "danger" | "neutral" | "accent" {
  if (!status) return "neutral";
  const s = status.toLowerCase();
  if (s === "sent") return "success";
  if (s === "approved") return "accent";
  if (s === "pending_approval" || s === "queued" || s === "sending") return "warning";
  if (s === "failed" || s === "cancelled") return "danger";
  return "neutral";
}

export function formatAvailabilitySlotsForEmail(
  dailyAvailability: readonly DailyAvailability[],
): string {
  if (!dailyAvailability || dailyAvailability.length === 0) {
    return "• Tuesday & Thursday 10:00 AM – 2:00 PM CT\n• Wednesday 1:00 PM – 4:30 PM CT";
  }

  const lines: string[] = [];
  for (const day of dailyAvailability) {
    const slots = day.slots30min.slice(0, 3);
    if (slots.length > 0) {
      const slotTimes = slots.map((s) => s.formattedCt.replace(/^.*·\s*/u, "")).join(", ");
      lines.push(`• ${day.dayName}, ${day.dateStr}: ${slotTimes}`);
    }
  }

  return lines.length > 0
    ? lines.join("\n")
    : "• Tuesday & Thursday 10:00 AM – 2:00 PM CT\n• Wednesday 1:00 PM – 4:30 PM CT";
}

export function applyRecruiterPillToComposer(
  pill: RecruiterPillReply,
  recipientAddress: string,
  recipientName?: string,
): ComposeMessageInput {
  return {
    recipientAddress,
    recipientName: recipientName ?? "",
    subject: pill.subject,
    bodyText: pill.bodyText,
    bodyHtml: pill.bodyHtml ?? undefined,
    channel: "gmail",
  };
}

export function filterMessages(
  messages: readonly OutboxMessage[],
  criteria: MessageFilterCriteria,
): OutboxMessage[] {
  let filtered = [...messages];

  if (criteria.channel && criteria.channel !== "all" && criteria.channel !== "") {
    filtered = filtered.filter(
      (m) => m.channel.toLowerCase() === criteria.channel?.toLowerCase(),
    );
  }

  if (criteria.status && criteria.status !== "all" && criteria.status !== "") {
    filtered = filtered.filter(
      (m) => m.status.toLowerCase() === criteria.status?.toLowerCase(),
    );
  }

  if (criteria.search && criteria.search.trim() !== "") {
    const q = criteria.search.toLowerCase().trim();
    filtered = filtered.filter((m) => {
      const matchSubject = m.subject.toLowerCase().includes(q);
      const matchBody = m.bodyText.toLowerCase().includes(q);
      const matchRecipient = m.recipientAddress.toLowerCase().includes(q);
      const matchName = m.recipientName?.toLowerCase().includes(q) ?? false;
      return matchSubject || matchBody || matchRecipient || matchName;
    });
  }

  return filtered;
}

export function inboxEmptyState(criteria: MessageFilterCriteria): {
  title: string;
  description: string;
} {
  const hasFilter =
    (criteria.channel && criteria.channel !== "all" && criteria.channel !== "") ||
    (criteria.status && criteria.status !== "all" && criteria.status !== "") ||
    Boolean(criteria.search?.trim());

  if (!hasFilter) {
    return {
      title: "Inbox is clean",
      description: "No recruiter messages or communication threads currently pending.",
    };
  }
  return {
    title: "No messages match filters",
    description: "No messages match your selected channel or search criteria. Reset filters to view all communication threads.",
  };
}
