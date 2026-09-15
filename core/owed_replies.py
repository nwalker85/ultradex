"""Owed replies → Odin's Runes action items.

The bridge between the mail ranker (`core.mail_ranking`) and the Odin's Runes
task hub (`amp-live-aid` `/api/tasks`). Pure functions only — the CLI in
`cli/owed_replies.py` owns every socket.

Two things live here that the ranker deliberately does not do:

1. **Name fallback for the contact directory.** The ranker matches contacts on
   the exact address, which is the right rule when the mirror carries
   addresses. Today the Dex mirror carries an email for 3 of 2,265 contacts, so
   an address-only directory is structurally blind. `CccContactDirectory`
   matches by address first and falls back to the sender's *display name*
   against `contacts.name` — recorded as such on the task so the operator can
   see which rule fired.

2. **The task shape.** One action item per owed thread, keyed on the message id
   so re-runs are idempotent, with the ranker's own explanation carried as the
   context snippet. The hub's `INSERT OR REPLACE` would reset a completed task
   to pending, so the sync plan skips ids the hub already holds.

3. **The task follows the thread's tail.** When someone else writes into a
   thread that already has an open task (2026-09-14: Mark replied in
   Michelle's thread), the plan *updates* that task's title and description
   rather than raising a second one — and only raises a fresh task once the
   old one is closed. A closed task means the operator ruled; a new inbound
   message reopens the question, not the ruling.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .mail_ranking import KnownContact, MailRankResult, MODE_OWED_REPLY
from .mail_reads import MailMessage, normalize_address

CLOSED_STATUSES = frozenset({"completed", "rejected", "withdrawn", "unresolved", "done", "cancelled"})
RELAY_REPLY_URLS = {"substack": "https://substack.com/inbox"}

TASK_SOURCE = "ccc_email"
TASK_ID_PREFIX = "ccc-email-"

_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "mba", "ains", "cpcu"}

# The Dex mirror also holds auto-imported senders ("Dex", "LinkedIn", "Spectrum",
# "Nextdoor Local News") as if they were people. The name fallback must not turn
# a newsletter into a debt, so it only fires for a person-shaped display name on
# an address that does not look like a bulk sender. Heuristic, and recorded as
# `contact_matched_by = "name"` on the task so the operator can see it fired.
_BULK_LOCAL_PARTS = {
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply", "notify", "notification",
    "notifications", "updates", "update", "news", "newsletter", "newsletters", "digest", "info",
    "hello", "hi", "team", "support", "help", "marketing", "promo", "promotions", "offers",
    "sales", "billing", "myaccount", "account", "accounts", "alerts", "alert", "mailer",
    "mail", "email", "reply", "jobs", "jobs-noreply", "progress", "reports", "invitations",
    "messages-noreply", "customerservice", "service", "orders", "order", "shipping",
}
_BULK_LOCAL_TOKENS = ("noreply", "no-reply", "donotreply", "notification", "newsletter", "mailer", "bounce", "campaign")


def looks_like_bulk_sender(address: str) -> bool:
    local, _, domain = normalize_address(address).partition("@")
    if not local or not domain:
        return True
    if local in _BULK_LOCAL_PARTS or any(tok in local for tok in _BULK_LOCAL_TOKENS):
        return True
    # Sub-domains carved out for mass mail: rs.email.x, updates.x, mail.x, em.x, e.x
    labels = domain.split(".")
    if len(labels) > 2 and labels[0] in {"email", "e", "em", "mail", "updates", "news", "notify", "rs", "info", "go", "click", "t", "m"}:
        return True
    return False


def person_shaped(name: str) -> bool:
    """Two to four word tokens, none of them obviously an organisation word."""
    tokens = normalize_name(name).split()
    if not 2 <= len(tokens) <= 4:
        return False
    org_words = {"news", "team", "reports", "report", "digest", "local", "inc", "llc", "ltd", "co", "company", "support", "notifications", "lifestyle", "collectibles", "supply", "insurance"}
    return not any(t in org_words for t in tokens)


def normalize_name(raw: str | None) -> str:
    """`"Michelle Foster Earle"` -> `"michelle foster earle"`.

    Case- and accent-insensitive, punctuation dropped, credential suffixes
    (`AINS`, `PhD`, …) removed so `"Wesley Earle, AINS"` and `"Wesley Earle"`
    meet. Deliberately does not collapse middle names: `"Michelle Earle"` and
    `"Michelle Foster Earle"` stay distinct, and `_name_keys` handles that.
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    tokens = [t for t in text.split() if t not in _NAME_SUFFIXES]
    return " ".join(tokens)


def _name_keys(name: str) -> set[str]:
    """Every key a contact answers to: the full name and first+last."""
    full = normalize_name(name)
    if not full:
        return set()
    keys = {full}
    parts = full.split()
    if len(parts) > 2:
        keys.add(f"{parts[0]} {parts[-1]}")
    return keys


@dataclass(frozen=True)
class ContactRow:
    """One row of the CCC `/api/v1/contacts` response — the fields we read."""

    id: str
    name: str
    email: str | None = None
    company: str | None = None
    job_title: str | None = None

    @property
    def is_person(self) -> bool:
        """Dex rows that came from a real relationship carry a company or a
        job title (1,617 of 2,265 on 2026-09-14). Rows it auto-imported from
        mail senders ("Advance Auto Parts", "Chewy.com", "Abel Moreno") carry
        neither. That, plus a person-shaped name, is the name-fallback gate."""
        return bool(self.company or self.job_title) and person_shaped(self.name)


@dataclass
class CccContactDirectory:
    """`ContactDirectory` over CCC contact rows, with a display-name fallback.

    `lookup()` only receives addresses (that is the ranker's contract), so the
    display names have to be registered beforehand via `observe()` — the CLI
    wraps the corpus so every message the ranker reads passes through it.
    """

    by_email: dict[str, KnownContact] = field(default_factory=dict)
    by_name: dict[str, KnownContact] = field(default_factory=dict)
    company_by_contact: dict[str, str] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)
    matched_by: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows: Iterable[ContactRow]) -> "CccContactDirectory":
        directory = cls()
        for row in rows:
            contact = KnownContact(contact_id=row.id, name=row.name, email=normalize_address(row.email))
            if row.company:
                directory.company_by_contact[row.id] = row.company
            if contact.email and contact.email not in directory.by_email:
                directory.by_email[contact.email] = contact
            if not row.is_person:
                continue  # sender rows Dex imported from mail, not relationships
            for key in _name_keys(row.name):
                # First writer wins; a duplicate name is ambiguous and we keep
                # the first rather than guess. Dex is the place to fix that.
                directory.by_name.setdefault(key, contact)
        return directory

    def observe(self, messages: Iterable[MailMessage]) -> None:
        for message in messages:
            address = normalize_address(message.from_addr)
            if address and message.from_name and address not in self.display_names:
                self.display_names[address] = message.from_name

    def lookup(self, addresses: Sequence[str]) -> Mapping[str, KnownContact]:
        found: dict[str, KnownContact] = {}
        for raw in addresses:
            address = normalize_address(raw)
            if not address or address in found:
                continue
            contact = self.by_email.get(address)
            if contact is not None:
                found[address] = contact
                self.matched_by[address] = "email"
                continue
            display = self.display_names.get(address)
            if not display or not person_shaped(display) or looks_like_bulk_sender(address):
                continue
            for key in _name_keys(display):
                contact = self.by_name.get(key)
                if contact is not None:
                    found[address] = KnownContact(
                        contact_id=contact.contact_id,
                        name=contact.name,
                        email=address,
                        relationship_tier=contact.relationship_tier,
                        organization_id=contact.organization_id,
                    )
                    self.matched_by[address] = "name"
                    break
        return found

    def company_for(self, contact: KnownContact | None) -> str | None:
        if contact is None:
            return None
        return self.company_by_contact.get(contact.contact_id)


class ObservingCorpus:
    """Wraps a `MailCorpus` so every message read is shown to the directory."""

    def __init__(self, corpus, directory: CccContactDirectory) -> None:
        self._corpus = corpus
        self._directory = directory

    def recent_messages(self, **kwargs):
        rows = list(self._corpus.recent_messages(**kwargs))
        self._directory.observe(rows)
        return rows

    def latest_messages_per_thread(self, **kwargs):
        rows = list(self._corpus.latest_messages_per_thread(**kwargs))
        self._directory.observe(rows)
        return rows

    def thread_messages(self, thread_ids):
        rows = list(self._corpus.thread_messages(thread_ids))
        self._directory.observe(rows)
        return rows

    def threads_with_message_from(self, thread_ids, addresses):
        return self._corpus.threads_with_message_from(thread_ids, addresses)


class UnionCorpus:
    """One `MailCorpus` over several per-account databases.

    The ingest side keeps one database per mail account (b58e885); an operator
    with two addresses owes replies in both. Reads concatenate, sorted newest
    first and cut at `limit`; the replied-thread read unions.
    """

    def __init__(self, corpora: Sequence) -> None:
        if not corpora:
            raise ValueError("UnionCorpus needs at least one corpus")
        self._corpora = list(corpora)

    def _merged(self, method: str, **kwargs):
        limit = kwargs.get("limit")
        rows = []
        for corpus in self._corpora:
            rows.extend(getattr(corpus, method)(**kwargs))
        rows.sort(key=lambda m: (m.ts, m.message_id), reverse=True)
        return rows[:limit] if limit else rows

    def recent_messages(self, **kwargs):
        return self._merged("recent_messages", **kwargs)

    def latest_messages_per_thread(self, **kwargs):
        return self._merged("latest_messages_per_thread", **kwargs)

    def thread_messages(self, thread_ids):
        rows = []
        for corpus in self._corpora:
            rows.extend(corpus.thread_messages(thread_ids))
        rows.sort(key=lambda m: (m.ts, m.message_id))
        return rows

    def threads_with_message_from(self, thread_ids, addresses):
        found: set[str] = set()
        for corpus in self._corpora:
            found |= set(corpus.threads_with_message_from(thread_ids, addresses))
        return frozenset(found)


def task_id_for(message_id: str) -> str:
    return TASK_ID_PREFIX + message_id


def _priority(result: MailRankResult) -> str:
    if result.score >= 90:
        return "high"
    if result.score >= 70:
        return "medium"
    return "low"


def task_payload(
    result: MailRankResult,
    *,
    contact: KnownContact | None,
    company: str | None,
    matched_by: str | None,
    display_name: str | None,
) -> dict[str, Any]:
    """The `/api/tasks` body for one owed reply. Stable for a given message.

    The title names the person who wrote (the sender's display name); the
    contact fields name the relationship the thread is with. Usually the same
    person; when a colleague writes into a contact's thread they differ, and
    `contact_matched_by = "thread"` says so. A relayed direct message names the
    counterparty and says where the reply happens.
    """
    subject = result.subject.strip() or "(no subject)"
    age = int(round(result.age_days))
    if result.relay:
        who = result.contact_name or display_name or result.from_addr
        channel = result.relay.capitalize()
        subject = subject.replace("💬", "").strip() or "(no subject)"
        url = RELAY_REPLY_URLS.get(result.relay, "")
        return {
            "id": task_id_for(result.message_id),
            "title": f"Reply on {channel} to {who}: {subject}",
            "description": (
                f"{who} sent you a direct message on {channel} {age} day{'s' if age != 1 else ''} ago "
                f"and the mailbox cannot see whether you answered. Reply there: {url}\n"
                f"Ranker: {result.explanation}"
            ),
            "assignee": "Nate",
            "status": "pending",
            "priority": _priority(result),
            "source": TASK_SOURCE,
            "source_ref": result.message_id,
            "suggested_action": "reply",
            "confidence": round(min(result.score, 100) / 100, 2),
            "contact_id": None,
            "contact_name": who,
            "organization_name": None,
            "context_snippet": result.explanation,
            "raw_metadata": {
                "thread_id": result.thread_id,
                "from_addr": result.from_addr,
                "message_ts": result.ts.isoformat(),
                "score": result.score,
                "mode": result.mode,
                "age_days": round(result.age_days, 1),
                "contact_matched_by": None,
                "relay": result.relay,
                "reply_url": url,
            },
        }
    via_thread = contact is not None and matched_by == "thread"
    who = (display_name if via_thread else None) or (contact.name if contact else None) \
        or display_name or result.from_addr
    return {
        "id": task_id_for(result.message_id),
        "title": f"Reply to {who}: {subject}",
        "description": (
            f"{who} has had the last word on this thread for {age} day{'s' if age != 1 else ''}. "
            + (f"The thread is with {contact.name}"  # type: ignore[union-attr]
               + (f" ({company})" if company else "") + ". " if via_thread else "")
            + f"Ranker: {result.explanation}"
        ),
        "assignee": "Nate",
        "status": "pending",
        "priority": _priority(result),
        "source": TASK_SOURCE,
        "source_ref": result.message_id,
        "suggested_action": "reply",
        "confidence": round(min(result.score, 100) / 100, 2),
        "contact_id": contact.contact_id if contact else None,
        "contact_name": contact.name if contact else display_name,
        "organization_name": company,
        "context_snippet": result.explanation,
        "raw_metadata": {
            "thread_id": result.thread_id,
            "from_addr": result.from_addr,
            "message_ts": result.ts.isoformat(),
            "score": result.score,
            "mode": result.mode,
            "age_days": round(result.age_days, 1),
            "contact_matched_by": matched_by,
        },
    }


@dataclass(frozen=True)
class SyncPlan:
    create: tuple[dict[str, Any], ...]
    skipped_existing: tuple[str, ...]
    ignored: tuple[str, ...]  # surfaced but not owed
    # PATCH bodies for tasks whose thread moved on: {"id", "title", "description", "raw_metadata"}
    update: tuple[dict[str, Any], ...] = ()


def _payload_for(result: MailRankResult, directory: CccContactDirectory) -> dict[str, Any]:
    address = normalize_address(result.from_addr)
    contact = directory.lookup([address]).get(address)
    matched_by = directory.matched_by.get(address)
    if contact is None and result.contact_id and not result.relay:
        # The ranker reached a contact through the thread (cc, or an earlier
        # sender), not through this sender. Link that relationship.
        contact = KnownContact(contact_id=result.contact_id, name=result.contact_name or "",
                               email="", via="thread")
        matched_by = "thread"
    return task_payload(
        result,
        contact=contact,
        company=directory.company_for(contact),
        matched_by=matched_by,
        display_name=directory.display_names.get(address),
    )


def plan_sync(
    results: Sequence[MailRankResult],
    *,
    directory: CccContactDirectory,
    existing_task_ids: Iterable[str] | Mapping[str, str],
    include_arrivals: bool = False,
) -> SyncPlan:
    """Decide what to post. Owed replies only unless `include_arrivals`.

    `existing_task_ids` is either a bare iterable of hub task ids (all treated
    as open) or a mapping id -> hub status, which lets the plan tell an open
    task from a closed one when a thread's tail moves.
    """
    if isinstance(existing_task_ids, Mapping):
        existing: dict[str, str] = {k: (v or "") for k, v in existing_task_ids.items()}
    else:
        existing = {task_id: "" for task_id in existing_task_ids}
    # thread -> the open hub task keyed on an OLDER message of that thread
    open_task_by_thread: dict[str, str] = {}
    for result in results:
        task_id = task_id_for(result.message_id)
        if task_id in existing and existing[task_id].lower() not in CLOSED_STATUSES:
            open_task_by_thread.setdefault(result.thread_id, task_id)

    create: list[dict[str, Any]] = []
    update: list[dict[str, Any]] = []
    skipped: list[str] = []
    ignored: list[str] = []
    for result in results:
        if not result.surfaced:
            continue
        if result.mode != MODE_OWED_REPLY and not include_arrivals:
            ignored.append(result.message_id)
            continue
        task_id = task_id_for(result.message_id)
        if task_id in existing:
            skipped.append(task_id)
            continue
        payload = _payload_for(result, directory)
        older = open_task_by_thread.get(result.thread_id)
        if older is not None and older != task_id:
            update.append({
                "id": older,
                "title": payload["title"],
                "description": payload["description"],
                "raw_metadata": {**payload["raw_metadata"], "source_ref": result.message_id},
            })
            continue
        create.append(payload)
    return SyncPlan(create=tuple(create), skipped_existing=tuple(skipped),
                    ignored=tuple(ignored), update=tuple(update))
