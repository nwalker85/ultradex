import type { CommunicationEntry, Contact } from "@ultradex/sdk";

export const CONTACT_RELATIONSHIP_TIERS = [
  "champion",
  "advocate",
  "peer",
  "recruiter",
  "lead",
  "unknown",
] as const;

export type RelationshipTier = (typeof CONTACT_RELATIONSHIP_TIERS)[number];

export interface ContactFilterCriteria {
  readonly search?: string;
  readonly tier?: string;
  readonly minAdvocacyScore?: number | null;
  readonly onlyNeglected?: boolean;
  readonly organizationId?: string;
}

export function isNeglectedContact(contact: Contact, now = new Date()): boolean {
  if (contact.aiValue === null || contact.aiValue === undefined || contact.aiValue < 60) {
    return false;
  }
  if (!contact.lastContacted) {
    return true;
  }
  const lastContactMs = Date.parse(contact.lastContacted);
  if (Number.isNaN(lastContactMs)) {
    return true;
  }
  const diffDays = (now.getTime() - lastContactMs) / (1000 * 60 * 60 * 24);
  return diffDays >= 30;
}

export function relationshipTierTone(
  tier: string | null | undefined,
): "success" | "accent" | "warning" | "neutral" {
  if (!tier) return "neutral";
  const normalized = tier.toLowerCase();
  if (normalized === "champion") return "success";
  if (normalized === "advocate") return "accent";
  if (normalized === "recruiter") return "warning";
  if (normalized === "peer") return "neutral";
  return "neutral";
}

export function filterContacts(
  contacts: readonly Contact[],
  criteria: ContactFilterCriteria,
): Contact[] {
  let filtered = [...contacts];

  if (criteria.organizationId) {
    filtered = filtered.filter((c) => c.organizationId === criteria.organizationId);
  }

  if (criteria.tier && criteria.tier !== "") {
    filtered = filtered.filter(
      (c) => c.relationshipTier?.toLowerCase() === criteria.tier?.toLowerCase(),
    );
  }

  if (
    criteria.minAdvocacyScore !== undefined &&
    criteria.minAdvocacyScore !== null &&
    criteria.minAdvocacyScore > 0
  ) {
    filtered = filtered.filter(
      (c) =>
        c.advocacyScore !== null &&
        c.advocacyScore !== undefined &&
        c.advocacyScore >= (criteria.minAdvocacyScore ?? 0),
    );
  }

  if (criteria.onlyNeglected) {
    filtered = filtered.filter((c) => isNeglectedContact(c));
  }

  if (criteria.search && criteria.search.trim() !== "") {
    const q = criteria.search.toLowerCase().trim();
    filtered = filtered.filter((c) => {
      const matchName = c.name.toLowerCase().includes(q);
      const matchCompany = c.company?.toLowerCase().includes(q) ?? false;
      const matchTitle = c.jobTitle?.toLowerCase().includes(q) ?? false;
      const matchEmail = c.email?.toLowerCase().includes(q) ?? false;
      const matchNotes = c.notes?.toLowerCase().includes(q) ?? false;
      return matchName || matchCompany || matchTitle || matchEmail || matchNotes;
    });
  }

  return filtered;
}

export function sortCommunicationHistoryDesc(
  history: readonly CommunicationEntry[],
): CommunicationEntry[] {
  return [...history].sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
}

export function contactsEmptyState(criteria: ContactFilterCriteria): {
  title: string;
  description: string;
} {
  const hasFilter =
    Boolean(criteria.search?.trim()) ||
    Boolean(criteria.tier) ||
    Boolean(criteria.minAdvocacyScore) ||
    Boolean(criteria.onlyNeglected);

  if (!hasFilter) {
    return {
      title: "No contacts found",
      description: "Import or sync Dex contacts to populate the sovereign network directory.",
    };
  }
  return {
    title: "No matching contacts",
    description: "No contacts match your active filter and search criteria. Reset filters to view all records.",
  };
}

export function findContactById(
  contacts: readonly Contact[],
  id: string,
): Contact | null {
  return contacts.find((c) => c.id === id) ?? null;
}
