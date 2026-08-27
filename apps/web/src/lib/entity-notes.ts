export type EntityNoteType =
  | "contact"
  | "organization"
  | "relationship"
  | "opportunity"
  | "application"
  | "lead";

export interface EntityNote {
  readonly noteId: string;
  readonly entityType: EntityNoteType;
  readonly entityId: string;
  readonly submittedBy: string;
  readonly category: string | null;
  readonly disposition: string | null;
  readonly assignedTo: string | null;
  readonly comment: string;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface CreateEntityNoteInput {
  readonly entityType: EntityNoteType;
  readonly entityId: string;
  readonly comment: string;
  readonly category?: string;
  readonly disposition?: string;
  readonly assignedTo?: string;
}

type RawEntityNote = {
  note_id: string;
  entity_type: EntityNoteType;
  entity_id: string;
  submitted_by: string;
  category: string | null;
  disposition: string | null;
  assigned_to: string | null;
  comment: string;
  created_at: string;
  updated_at: string;
};

function mapNote(raw: RawEntityNote): EntityNote {
  return {
    noteId: raw.note_id,
    entityType: raw.entity_type,
    entityId: raw.entity_id,
    submittedBy: raw.submitted_by,
    category: raw.category,
    disposition: raw.disposition,
    assignedTo: raw.assigned_to,
    comment: raw.comment,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export async function listEntityNotes(
  baseUrl: string,
  token: string,
  entityType: EntityNoteType,
  entityId: string,
): Promise<EntityNote[]> {
  const url = new URL("/api/v2/entity-notes", baseUrl.replace(/\/$/u, ""));
  url.searchParams.set("entity_type", entityType);
  url.searchParams.set("entity_id", entityId);
  const headers: Record<string, string> = {};
  if (token.trim()) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`Failed to load notes (${response.status})`);
  }
  const data = (await response.json()) as RawEntityNote[];
  return data.map(mapNote);
}

export async function createEntityNote(
  baseUrl: string,
  token: string,
  input: CreateEntityNoteInput,
): Promise<EntityNote> {
  const url = new URL("/api/v2/entity-notes", baseUrl.replace(/\/$/u, ""));
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token.trim()) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({
      entity_type: input.entityType,
      entity_id: input.entityId,
      comment: input.comment,
      category: input.category ?? null,
      disposition: input.disposition ?? null,
      assigned_to: input.assignedTo ?? null,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to create note (${response.status})`);
  }
  return mapNote((await response.json()) as RawEntityNote);
}
