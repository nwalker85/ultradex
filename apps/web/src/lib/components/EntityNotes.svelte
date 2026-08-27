<script lang="ts">
  import { Button, Field, Panel } from "@ravenhelm/ui-svelte";

  import {
    createEntityNote,
    listEntityNotes,
    type EntityNote,
    type EntityNoteType,
  } from "$lib/entity-notes";
  import type { GlassConfig } from "$lib/client";
  import { operatorAuthMissing, SAME_ORIGIN_PROXY_SENTINEL } from "$lib/client";
  import ErrorBanner from "$lib/components/ErrorBanner.svelte";

  let {
    config,
    entityType,
    entityId,
    title = "Notes",
  }: {
    config: GlassConfig;
    entityType: EntityNoteType;
    entityId: string;
    title?: string;
  } = $props();

  let notes = $state<EntityNote[]>([]);
  let loading = $state(false);
  let submitting = $state(false);
  let error = $state<unknown>(null);
  let comment = $state("");
  let category = $state("");
  let disposition = $state("");
  let assignedTo = $state("");

  const tokenMissing = $derived(operatorAuthMissing(config));
  const authToken = $derived(
    config.token.trim() || SAME_ORIGIN_PROXY_SENTINEL,
  );

  async function refresh(): Promise<void> {
    if (tokenMissing || !entityId) return;
    loading = true;
    error = null;
    try {
      notes = await listEntityNotes(
        config.baseUrl,
        authToken,
        entityType,
        entityId,
      );
    } catch (cause) {
      error = cause;
    } finally {
      loading = false;
    }
  }

  async function submitNote(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (tokenMissing || !comment.trim()) return;
    submitting = true;
    error = null;
    try {
      await createEntityNote(config.baseUrl, authToken, {
        entityType,
        entityId,
        comment,
        category: category.trim() || undefined,
        disposition: disposition.trim() || undefined,
        assignedTo: assignedTo.trim() || undefined,
      });
      comment = "";
      await refresh();
    } catch (cause) {
      error = cause;
    } finally {
      submitting = false;
    }
  }

  $effect(() => {
    entityId;
    entityType;
    void refresh();
  });
</script>

<Panel {title} meta={notes.length ? `${notes.length} note(s)` : "No notes yet"}>
  {#if error}
    <ErrorBanner {error} />
  {/if}

  {#if loading && notes.length === 0}
    <p class="ccc-empty">Loading notes…</p>
  {:else if notes.length === 0}
    <p class="ccc-empty">No notes for this record yet.</p>
  {:else}
    <ul class="ccc-notes-list">
      {#each notes as note (note.noteId)}
        <li class="ccc-notes-list__item">
          <div class="ccc-notes-list__meta">
            <strong>{note.submittedBy}</strong>
            <time datetime={note.createdAt}>{new Date(note.createdAt).toLocaleString()}</time>
          </div>
          {#if note.category || note.disposition || note.assignedTo}
            <div class="ccc-notes-list__tags">
              {#if note.category}<span>Category: {note.category}</span>{/if}
              {#if note.disposition}<span>Disposition: {note.disposition}</span>{/if}
              {#if note.assignedTo}<span>Assigned: {note.assignedTo}</span>{/if}
            </div>
          {/if}
          <p>{note.comment}</p>
        </li>
      {/each}
    </ul>
  {/if}

  <form class="ccc-notes-form" onsubmit={submitNote}>
    <Field label="Comment" bind:value={comment} required />
    <div class="ccc-notes-form__optional">
      <Field label="Category (optional)" bind:value={category} />
      <Field label="Disposition (optional)" bind:value={disposition} />
      <Field label="Assigned to (optional)" bind:value={assignedTo} />
    </div>
    <Button type="submit" disabled={submitting || tokenMissing || !comment.trim()}>
      {submitting ? "Saving…" : "Add note"}
    </Button>
  </form>
</Panel>

<style>
  .ccc-notes-list {
    list-style: none;
    margin: 0 0 1rem;
    padding: 0;
    display: grid;
    gap: 0.75rem;
  }
  .ccc-notes-list__item {
    border: 1px solid var(--ccc-border, #2a2a2a);
    border-radius: 0.5rem;
    padding: 0.75rem;
  }
  .ccc-notes-list__meta {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    font-size: 0.85rem;
    margin-bottom: 0.35rem;
  }
  .ccc-notes-list__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: 0.8rem;
    opacity: 0.85;
    margin-bottom: 0.35rem;
  }
  .ccc-notes-form {
    display: grid;
    gap: 0.75rem;
    margin-top: 1rem;
  }
  .ccc-notes-form__optional {
    display: grid;
    gap: 0.5rem;
  }
  @media (min-width: 48rem) {
    .ccc-notes-form__optional {
      grid-template-columns: repeat(3, 1fr);
    }
  }
</style>
