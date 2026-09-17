"""Turn LinkedIn threads into Odin's Runes tasks — the LinkedIn twin of
`core.owed_replies`.

A thread is an owed reply when its last message is inbound, older than the
grace period, and not from LinkedIn itself. A direct message is a person by
construction (the same reasoning the email ranker applies to relays), so a
known-contact match raises confidence but is not required.

Task ids are per (thread, last inbound message): a new inbound message after
Nate replied is a new task; the same message on the next scan is the same id
and is skipped. Threads whose last message is now Nate's close any open task
the producer holds for that thread.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

from .linkedin_reads import LinkedInThread
from .owed_replies import CLOSED_STATUSES, CccContactDirectory, _name_keys

TASK_SOURCE = "ccc_linkedin"
TASK_ID_PREFIX = "ccc-linkedin-"
RELAY = "linkedin"
DEFAULT_GRACE = timedelta(hours=24)
COLD_GRACE = timedelta(days=3)


MESSAGING_ROOT = "https://www.linkedin.com/messaging/"


def task_id_for(thread: LinkedInThread) -> str:
    """Per (counterparty, last inbound message). Deliberately NOT keyed on the
    thread URL: URL resolution is a DOM click that can fail on one scan and
    succeed on the next, and an id that flips between the two would post the
    same owed message twice. The name and timestamp are what every scan has;
    the URL travels in `raw_metadata` when it was resolved."""
    key = f"name:{thread.counterparty.strip().lower()}\n{thread.last_message_at.isoformat()}"
    return TASK_ID_PREFIX + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def match_contact(directory: CccContactDirectory, name: str):
    for key in _name_keys(name):
        contact = directory.by_name.get(key)
        if contact is not None:
            return contact
    return None


@dataclass(frozen=True)
class RankedThread:
    thread: LinkedInThread
    owed: bool
    age: timedelta
    known: bool
    reason: str


def rank(threads: Iterable[LinkedInThread], *, directory: CccContactDirectory, now: datetime,
         grace: timedelta = DEFAULT_GRACE, cold_grace: timedelta = COLD_GRACE) -> list[RankedThread]:
    out: list[RankedThread] = []
    for thread in threads:
        age = now - thread.last_message_at
        known = match_contact(directory, thread.counterparty) is not None
        if thread.is_system:
            out.append(RankedThread(thread, False, age, known, "system sender"))
            continue
        if thread.last_message_from == "me":
            out.append(RankedThread(thread, False, age, known, "you wrote last"))
            continue
        needed = grace if known else cold_grace
        if age < needed:
            out.append(RankedThread(thread, False, age, known, f"inbound, within grace ({int(needed.total_seconds() // 3600)}h)"))
            continue
        out.append(RankedThread(thread, True, age, known, "owed reply: inbound past grace" + (", known contact" if known else "")))
    return out


def _fmt_date(ts: datetime) -> str:
    return f"{ts.strftime('%b')} {ts.day}"


def _excerpt(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def task_payload(ranked: RankedThread, *, directory: CccContactDirectory) -> dict[str, Any]:
    thread = ranked.thread
    contact = match_contact(directory, thread.counterparty)
    company = directory.company_by_contact.get(contact.contact_id) if contact else None
    who = contact.name if contact else thread.counterparty
    excerpt = _excerpt(thread.last_message_text)
    days = int(round(ranked.age.total_seconds() / 86400))
    date_str = _fmt_date(thread.last_message_at)
    if excerpt:
        description = f'{who} sent you a message on LinkedIn on {date_str}: "{excerpt}". '
    else:
        description = f"{who} sent you a message on LinkedIn on {date_str}. "
    if company:
        description += f"({company}.) "
    reply_url = thread.thread_url or MESSAGING_ROOT
    description += f"You have not replied in {days} day{'s' if days != 1 else ''}. Reply at {reply_url}"
    confidence = 0.9 if ranked.known else 0.7
    return {
        "id": task_id_for(thread),
        "title": f"Reply on LinkedIn to {who}: {excerpt or '(message)'}",
        "description": description,
        "description_source": TASK_SOURCE,
        "assignee": "Nate",
        "status": "pending",
        "priority": "high" if ranked.known else "medium",
        "source": TASK_SOURCE,
        "source_ref": thread.thread_url or f"linkedin:{thread.counterparty}",
        "suggested_action": "reply",
        "confidence": confidence,
        "contact_id": contact.contact_id if contact else None,
        "contact_name": who,
        "organization_name": company,
        "context_snippet": ranked.reason,
        "raw_metadata": {
            "relay": RELAY,
            "reply_url": reply_url,
            "thread_url": thread.thread_url,
            "last_message_at": thread.last_message_at.isoformat(),
            "last_message_from": thread.last_message_from,
            "unread": thread.unread,
            "time_label": thread.time_label,
            "age_days": round(ranked.age.total_seconds() / 86400, 1),
            "contact_matched_by": "name" if contact else None,
        },
    }


@dataclass
class SyncPlan:
    create: list[dict[str, Any]] = field(default_factory=list)
    close: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)


def plan_sync(ranked: Sequence[RankedThread], *, directory: CccContactDirectory,
              existing: Mapping[str, Mapping[str, Any]]) -> SyncPlan:
    """`existing` maps hub task id -> {"status", "thread_url", "contact_name"}
    for this producer's tasks. Create for owed threads the hub does not hold;
    close open tasks whose thread Nate has since answered (matched by thread
    URL when both sides have one, else by counterparty name, since the scan
    does not resolve URLs for answered threads); skip ids already posted."""
    plan = SyncPlan()
    open_by_thread: dict[str, list[str]] = {}
    open_by_name: dict[str, list[str]] = {}
    for task_id, row in existing.items():
        if str(row.get("status") or "").lower() in CLOSED_STATUSES:
            continue
        url = str(row.get("thread_url") or "")
        if url:
            open_by_thread.setdefault(url, []).append(task_id)
        name = str(row.get("contact_name") or "").strip().lower()
        if name:
            open_by_name.setdefault(name, []).append(task_id)
    for item in ranked:
        thread = item.thread
        if not item.owed:
            plan.ignored.append(thread.thread_url or thread.counterparty)
            if thread.last_message_from == "me":
                if thread.thread_url and thread.thread_url in open_by_thread:
                    plan.close.extend(open_by_thread[thread.thread_url])
                else:
                    plan.close.extend(open_by_name.get(thread.counterparty.strip().lower(), []))
            continue
        task_id = task_id_for(thread)
        if task_id in existing:
            plan.skipped.append(task_id)
            continue
        plan.create.append(task_payload(item, directory=directory))
    plan.close = sorted(set(plan.close))
    return plan
