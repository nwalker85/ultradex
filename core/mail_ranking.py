"""The stupid ranker — deliberately un-clever surfacing for AAL Sense mail.

No ML, no embeddings, no model call. There are no training labels today, so
the loop has to run and produce promote/discard decisions *first*; those
decisions become the labels. Anything learned belongs downstream of this file,
never inside it.

## Silence is the signal, not arrival

The first cut of this ranker scored what *arrived*. That is the wrong half of
the problem. The operator's actual failure mode is threads where the ball has
been in **his** court and stayed there: a Google recruiter asked for his
availability on 2026-03-06, he never replied, the role died — five months
outstanding and nothing in the system ever said so. An arrival-only ranker is
structurally blind to that, because the defining property of an owed reply is
that nothing new has happened.

So there are two modes, and which one applies depends on whose court the ball
is in:

    ball in THEIR court (something arrived)
        score = 70 * recency * known_contact * replied_thread

    ball in YOUR court (you owe a reply)
        score = 72 + 28 * staleness

The time factor **inverts** between them. For an arrival, age is decay: a
five-month-old message is nearly worthless. For an owed reply, age is the
whole point — five months is five months of a door closing — so staleness
*rises* with age. Reusing the arrival decay curve here would score the Google
thread at ~0, which is exactly how it was missed.

The bands do not overlap: an arrival can never exceed 70, an owed reply never
falls below 72. **Any reply you owe outranks any mail that merely arrived.**
That is a one-sentence rule, which is the point.

Staleness rises linearly from the grace period to saturation, then plateaus,
and owed mode stops applying past the horizon. The horizon is what keeps a
two-year-dead thread from permanently owning the crown: past a year it is
archaeology, not an obligation, and it falls back to arrival scoring (where it
scores ~0). A plateau with no horizon would park dead threads at 100 forever —
the same avoidance failure `crown()` exists to prevent.

A cold open counts. An unanswered message from a known contact accrues the
debt whether or not the operator ever spoke in that thread (operator ruling,
2026-08-25): a known contact writing and getting silence is the failure mode
being designed against, not an edge case. See `owes_a_reply` for the four
conditions that remain, and for why the known-contact test has to be strict now
that it is the only thing separating a debt from a recruiter blast.

## Why the rule is un-clever on purpose

`DEFAULT_GMAIL_SENSE_QUERY` in `core/jobsearch_gmail.py` matches ATS sender
domains and six subject phrases. On 2026-08-25 it missed the operator's hiring
manager because the subject was ordinary, and it had already missed the Google
recruiter for five months because nothing about that thread was new. A
hand-authored query is a relevance model frozen at authoring time (design doc,
"Why not filter at ingest"). Neither miss needed a model to catch — both
needed the system to look at who and when instead of at words.

## Explainability

`MailRankResult.explanation` names every factor, its value, and why it took
that value — the same component-by-component contract
`DeterministicIntentScorer` holds itself to. A surfaced item must say why it
surfaced, because the operator's promote/discard on that item is the training
label, and a label attached to an unexplained score teaches nothing.

Weights are module constants with a `RankerConfig` override rather than
Intent-stored weights: this layer is corpus-wide, not career-specific (`mail`
is a corpus any vertical scores against), so it does not read the jobsearch
Intent singleton.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import AbstractSet, Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from .jobsearch_executors import DomainRefusal
from .mail_relays import relay_for
from .mail_reads import (
    DEFAULT_FETCH_LIMIT,
    MailCorpus,
    MailMessage,
    normalize_address,
)


MODE_ARRIVAL = "arrival"
MODE_OWED_REPLY = "owed_reply"
MODE_GATED = "gated"

# Recency half-life, arrival mode only. Seven days because a working week is
# the operator's own unit of "still live".
DEFAULT_RECENCY_HALF_LIFE_DAYS = 7.0

# Floor for a message from an address that is not in contacts. Low enough that
# a stranger never outranks a known contact of the same age and thread state,
# high enough that a stranger is still ranked rather than filtered out.
DEFAULT_UNKNOWN_SENDER_FLOOR = 0.35

# Floor for a thread the operator has never sent into.
DEFAULT_NO_REPLY_FLOOR = 0.55

# Recency never reaches zero: a three-year-old message (the corpus TTL) still
# ranks above nothing, so age alone can never make an item unsurfaceable.
DEFAULT_RECENCY_FLOOR = 0.01

# The two bands. They do not overlap, and that gap is the design: an owed
# reply always outranks an arrival, whatever the arrival is.
MAX_ARRIVAL_SCORE = 70
MIN_OWED_SCORE = 72
MAX_OWED_SCORE = 100

# You are allowed a few days to answer before it counts as owed.
DEFAULT_OWED_GRACE_DAYS = 3.0

# By here the owed factor is at full strength and stops rising. Beyond it,
# more silence does not make the item louder — it is already as loud as the
# scale goes.
DEFAULT_OWED_SATURATION_DAYS = 90.0

# Past here it is archaeology, not an obligation. Owed mode stops applying and
# the message falls back to arrival scoring, which by then is ~0. Without this
# a dead thread would sit at 100 forever and own the crown.
DEFAULT_OWED_HORIZON_DAYS = 365.0

# At or above this, the item is surfaced. See the table in the module tests.
DEFAULT_SURFACE_THRESHOLD = 30

# How far back the arrival sweep looks.
DEFAULT_WINDOW_DAYS = 14

# Gmail system labels that mean "the operator already made this decision".
SUPPRESSED_LABELS = frozenset({"SPAM", "TRASH", "DRAFT"})

# Addresses you cannot owe a reply to, because you cannot reply to them.
# Defence in depth behind the known-contact test: contact mirrors accumulate
# junk, and the day `no-reply@greenhouse.io` lands in `contacts` is the day an
# ATS blast would otherwise become a 100-scoring debt. Owed mode only — an
# arrival from a no-reply address is still legitimately ranked, just low.
UNREPLIABLE_LOCAL_PARTS = frozenset(
    {
        "no-reply",
        "noreply",
        "no_reply",
        "donotreply",
        "do-not-reply",
        "do_not_reply",
        "bounce",
        "bounces",
        "mailer-daemon",
        "postmaster",
        "notification",
        "notifications",
    }
)


@dataclass(frozen=True)
class RankerConfig:
    """Every knob in the rule. No hidden constants."""

    owner_addresses: frozenset[str] = frozenset()
    recency_half_life_days: float = DEFAULT_RECENCY_HALF_LIFE_DAYS
    unknown_sender_floor: float = DEFAULT_UNKNOWN_SENDER_FLOOR
    no_reply_floor: float = DEFAULT_NO_REPLY_FLOOR
    recency_floor: float = DEFAULT_RECENCY_FLOOR
    owed_grace_days: float = DEFAULT_OWED_GRACE_DAYS
    owed_saturation_days: float = DEFAULT_OWED_SATURATION_DAYS
    owed_horizon_days: float = DEFAULT_OWED_HORIZON_DAYS
    surface_threshold: int = DEFAULT_SURFACE_THRESHOLD
    suppressed_labels: frozenset[str] = SUPPRESSED_LABELS
    unrepliable_local_parts: frozenset[str] = UNREPLIABLE_LOCAL_PARTS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_addresses",
            frozenset(normalize_address(a) for a in self.owner_addresses) - {""},
        )
        if self.recency_half_life_days <= 0:
            raise ValueError("recency_half_life_days must be positive")
        if not 0 <= self.owed_grace_days < self.owed_saturation_days:
            raise ValueError("owed_grace_days must be below owed_saturation_days")
        if self.owed_horizon_days < self.owed_saturation_days:
            raise ValueError("owed_horizon_days must not be below owed_saturation_days")

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "RankerConfig":
        """`MAIL_OWNER_ADDRESSES` is a comma-separated list. No secrets here."""
        raw = environ.get("MAIL_OWNER_ADDRESSES") or ""
        config = cls(owner_addresses=frozenset(raw.split(",")))
        half_life = environ.get("MAIL_RANKER_HALF_LIFE_DAYS")
        threshold = environ.get("MAIL_RANKER_SURFACE_THRESHOLD")
        horizon = environ.get("MAIL_RANKER_OWED_HORIZON_DAYS")
        if half_life:
            config = replace(config, recency_half_life_days=float(half_life))
        if threshold:
            config = replace(config, surface_threshold=int(threshold))
        if horizon:
            config = replace(config, owed_horizon_days=float(horizon))
        return config


@dataclass(frozen=True)
class KnownContact:
    """A contacts-table hit. Dex is the system of record; `contacts` mirrors it."""

    contact_id: str
    name: str
    email: str
    relationship_tier: str | None = None
    organization_id: str | None = None
    # How the contact was reached when it is not the sender: "cc 'a@b'" /
    # "earlier in thread t" / "substack direct message". Recorded so the
    # explanation and the task can say which rule fired; None = the sender.
    via: str | None = None


class ContactDirectory(Protocol):
    """The one contacts read the ranker needs."""

    def lookup(self, addresses: Sequence[str]) -> Mapping[str, KnownContact]:
        """Map normalized address -> contact, for the addresses that are known."""


@dataclass(frozen=True)
class Debt:
    """When a thread's silence began and how many inbound messages it spans."""

    since: datetime
    count: int
    started_by: str  # normalized address of the first unanswered sender


@dataclass(frozen=True)
class RankFactor:
    label: str
    value: float
    detail: str

    def render(self) -> str:
        return f"{self.label} {self.value:.2f} ({self.detail})"


@dataclass(frozen=True)
class MailRankResult:
    """A ranked message and the reason it ranked there."""

    message_id: str
    thread_id: str
    ts: datetime
    from_addr: str
    subject: str
    score: int
    surfaced: bool
    explanation: str
    mode: str = MODE_ARRIVAL
    age_days: float = 0.0
    factors: tuple[RankFactor, ...] = ()
    risk_flags: tuple[str, ...] = ()
    contact_id: str | None = None
    contact_name: str | None = None
    relay: str | None = None  # "substack" when the mail carried a platform DM
    # Owed mode: when the silence began (the first unanswered inbound message
    # in the thread) and how many inbound messages have gone unanswered since.
    # `age_days` is measured from `debt_since`, so a follow-up never resets it.
    debt_since: datetime | None = None
    unanswered_count: int = 1

    @property
    def is_owed_reply(self) -> bool:
        return self.mode == MODE_OWED_REPLY


# --------------------------------------------------------------------------
# the rule
# --------------------------------------------------------------------------


def _age_days(message_ts: datetime, now: datetime) -> float:
    return max(0.0, (now - message_ts).total_seconds() / 86400.0)


def _recency_factor(age_days: float, config: RankerConfig) -> RankFactor:
    raw = 0.5 ** (age_days / config.recency_half_life_days)
    value = max(config.recency_floor, raw)
    if age_days < 1.0:
        aged = f"arrived {age_days * 24:.1f}h ago"
    else:
        aged = f"{age_days:.1f} days old"
    return RankFactor(
        "recency",
        value,
        f"{aged}, half-life {config.recency_half_life_days:g}d",
    )


def _staleness_factor(
    age_days: float,
    thread_id: str,
    config: RankerConfig,
    *,
    unanswered_count: int = 1,
    debt_started_by: str = "",
) -> RankFactor:
    """Rises with age, plateaus at saturation. The inverse of `_recency_factor`."""
    span = config.owed_saturation_days - config.owed_grace_days
    value = min(1.0, max(0.0, (age_days - config.owed_grace_days) / span))
    if unanswered_count > 1:
        detail = (
            f"thread {thread_id} has {unanswered_count} unanswered inbound messages; "
            f"the silence began {age_days:.1f} days ago with '{debt_started_by}' "
            f"(grace {config.owed_grace_days:g}d, saturates at {config.owed_saturation_days:g}d)"
        )
    else:
        detail = (
            f"last message in thread {thread_id} is inbound and unanswered for "
            f"{age_days:.1f} days (grace {config.owed_grace_days:g}d, "
            f"saturates at {config.owed_saturation_days:g}d)"
        )
    return RankFactor("owed_reply", value, detail)


def _contact_factor(
    contact: KnownContact | None,
    sender: str,
    config: RankerConfig,
) -> RankFactor:
    if contact is None:
        return RankFactor(
            "known_contact",
            config.unknown_sender_floor,
            f"sender '{sender}' is not in contacts",
        )
    tier = f", tier={contact.relationship_tier}" if contact.relationship_tier else ""
    return RankFactor(
        "known_contact",
        1.0,
        _contact_detail(contact, sender) + tier,
    )


def _contact_detail(contact: KnownContact, sender: str) -> str:
    """Who the contact is and how it was reached — the sender, or via whom."""
    if contact.via is None:
        return f"sender '{sender}' is contact '{contact.name}'"
    if contact.via.endswith("direct message"):
        return (
            f"'{sender}' relays a {contact.via} from '{contact.name}' — a person "
            f"addressing you by construction, not a blast; reply happens on "
            f"{contact.via.split()[0].capitalize()}, not in mail"
        )
    return (
        f"sender '{sender}' is not in contacts; thread is with contact "
        f"'{contact.name}' ({contact.via})"
    )


def _reply_factor(replied: bool, thread_id: str, config: RankerConfig) -> RankFactor:
    if replied:
        return RankFactor(
            "replied_thread",
            1.0,
            f"you have sent a message in thread {thread_id}",
        )
    return RankFactor(
        "replied_thread",
        config.no_reply_floor,
        f"you have never sent a message in thread {thread_id}",
    )


def is_unrepliable_address(address: str, config: RankerConfig) -> bool:
    """`no-reply@greenhouse.io` and friends. You cannot owe them anything."""
    local_part = normalize_address(address).split("@", 1)[0]
    return local_part in config.unrepliable_local_parts


def owes_a_reply(
    *,
    age_days: float,
    contact: KnownContact | None,
    is_thread_tail: bool,
    is_inbound: bool,
    config: RankerConfig,
) -> bool:
    """Is the ball in the operator's court on this thread, and has it sat?

    Four conditions, no cleverness:

    1. **Last word.** The message is the newest in its thread — nothing has
       happened since, which is what makes the silence *his*.
    2. **Inbound.** Someone else sent it. A thread where the operator sent the
       last word is not a debt no matter how old it is; the ball is in their
       court and waiting on them is not a failure of his.
    3. **Known contact.** Someone in `contacts`, matched on the exact address.
    4. **Aged, but not archaeology.** Older than the grace period, inside the
       horizon.

    Prior participation in the thread is deliberately **not** a condition
    (operator ruling, 2026-08-25). A known contact opening a thread and getting
    silence is *the* failure mode being designed against, not an edge case —
    two unanswered messages from the person who hired him at a previous
    company, two more from another contact, all cold opens. Requiring prior
    participation would make the ranker structurally blind to exactly those.

    That ruling puts the whole weight of the distinction on condition 3. The
    known-contact test is now the only thing between "you owe a reply" and
    "every unread recruiter blast is an obligation", so it is strict: an exact
    address match against the contacts mirror, never a domain or display-name
    match. Condition 3 also rejects addresses that cannot be replied to at all
    (see `is_unrepliable_address`), for the day a mass sender ends up in
    `contacts`.
    """
    return (
        is_thread_tail
        and is_inbound
        and contact is not None
        and not (contact.email and is_unrepliable_address(contact.email, config))
        and config.owed_grace_days < age_days <= config.owed_horizon_days
    )


def _gate(message: MailMessage, reason: str, flag: str, age_days: float) -> MailRankResult:
    return MailRankResult(
        message_id=message.message_id,
        thread_id=message.thread_id,
        ts=message.ts,
        from_addr=message.from_addr,
        subject=message.subject,
        score=0,
        surfaced=False,
        explanation=reason[:1000],
        mode=MODE_GATED,
        age_days=age_days,
        factors=(),
        risk_flags=(flag,),
    )


def score_message(
    message: MailMessage,
    *,
    now: datetime,
    contact: KnownContact | None,
    replied_to_thread: bool,
    is_thread_tail: bool,
    config: RankerConfig,
    debt: "Debt | None" = None,
) -> MailRankResult:
    """The rule. Pure — no I/O, operates on already-loaded rows.

    Same shape as `core/jobsearch_scoring.py::compute_score`: hard gates first,
    then components, then one explanation naming each component.

    `debt` dates the silence for owed mode: the first unanswered inbound
    message in the thread, not this one. A follow-up from the other side is one
    more person waiting, so it makes the debt older, never younger.
    """
    sender = normalize_address(message.from_addr)
    age_days = _age_days(message.ts, now)
    debt_age_days = _age_days(debt.since, now) if debt is not None else age_days
    debt_age_days = max(debt_age_days, age_days)

    if sender and sender in config.owner_addresses:
        return _gate(
            message,
            f"suppressed: you sent this message (from '{sender}')",
            "own_message",
            age_days,
        )

    suppressed = tuple(
        label for label in message.labels if label.upper() in config.suppressed_labels
    )
    if suppressed:
        return _gate(
            message,
            f"suppressed: label(s) {', '.join(suppressed)} — already decided",
            "label_suppressed",
            age_days,
        )

    # The owner gate above already returned, so anything reaching here is
    # inbound. The flag is passed explicitly anyway: `owes_a_reply` is public
    # and `StupidRanker.surface` calls it directly on thread tails that have
    # not been through the gate, where the direction test is doing real work.
    owed = owes_a_reply(
        age_days=debt_age_days,
        contact=contact,
        is_thread_tail=is_thread_tail,
        is_inbound=True,
        config=config,
    )

    if owed:
        staleness = _staleness_factor(
            debt_age_days, message.thread_id, config,
            unanswered_count=debt.count if debt else 1,
            debt_started_by=debt.started_by if debt else "",
        )
        # `known_contact` is the precondition that carries the whole weight of
        # owed mode, so it stays in `factors` and says so. `thread_history` is
        # context rather than a multiplier — since the 2026-08-25 ruling a cold
        # open accrues the same debt as an abandoned exchange, and the
        # explanation has to make clear which one the operator is looking at
        # without implying the difference moved the score.
        factors = (
            staleness,
            RankFactor(
                "known_contact",
                1.0,
                _contact_detail(contact, sender)  # type: ignore[arg-type]
                + (
                    f", tier={contact.relationship_tier}"  # type: ignore[union-attr]
                    if contact.relationship_tier  # type: ignore[union-attr]
                    else ""
                )
                + " (precondition of owed mode)",
            ),
            RankFactor(
                "thread_history",
                1.0,
                (
                    "the mailbox cannot see a reply sent on the platform — "
                    "triage closes this once you have answered there"
                    if contact is not None and contact.via is not None  # type: ignore[union-attr]
                    and contact.via.endswith("direct message")
                    else f"you have sent a message in thread {message.thread_id} before"
                    if replied_to_thread
                    else f"cold open — you have never replied in thread "
                    f"{message.thread_id}"
                )
                + " (context, not a multiplier)",
            ),
        )
        span = MAX_OWED_SCORE - MIN_OWED_SCORE
        score = round(MIN_OWED_SCORE + span * staleness.value)
        arithmetic = (
            f"score = {MIN_OWED_SCORE} + {span} x {staleness.value:.2f} = {score}"
        )
        risk_flags = ("owed_reply",)
    else:
        factors = (
            _recency_factor(age_days, config),
            _contact_factor(contact, sender or message.from_addr, config),
            _reply_factor(replied_to_thread, message.thread_id, config),
        )
        product = 1.0
        for factor in factors:
            product *= factor.value
        score = max(0, min(MAX_ARRIVAL_SCORE, round(MAX_ARRIVAL_SCORE * product)))
        arithmetic = (
            f"score = {MAX_ARRIVAL_SCORE} x "
            + " x ".join(f"{f.value:.2f}" for f in factors)
            + f" = {score}"
        )
        risk_flags = tuple(
            f"{factor.label}_absent" for factor in factors if factor.value < 1.0
        )

    explanation = "; ".join(factor.render() for factor in factors) + "; " + arithmetic
    if len(explanation) > 1000:
        explanation = explanation[:997] + "..."

    return MailRankResult(
        message_id=message.message_id,
        thread_id=message.thread_id,
        ts=message.ts,
        from_addr=message.from_addr,
        subject=message.subject,
        score=score,
        surfaced=score >= config.surface_threshold,
        explanation=explanation,
        mode=MODE_OWED_REPLY if owed else MODE_ARRIVAL,
        age_days=debt_age_days if owed else age_days,
        factors=factors,
        risk_flags=risk_flags,
        debt_since=(debt.since if debt else message.ts) if owed else None,
        unanswered_count=(debt.count if debt else 1) if owed else 1,
        contact_id=contact.contact_id if contact else None,
        contact_name=contact.name if contact else None,
        relay=(contact.via.split()[0] if contact and contact.via
               and contact.via.endswith("direct message") else None),
    )


def _sort_key(result: MailRankResult) -> tuple[float, float, str]:
    # Ties break toward the more *recent* arrival but the more *overdue* owed
    # reply — the same inversion the score uses. Modes never share a score, so
    # the two secondary scales never have to be compared against each other.
    secondary = (
        -result.ts.timestamp() if result.is_owed_reply else result.ts.timestamp()
    )
    return (result.score, secondary, result.message_id)


def rank_messages(
    messages: Sequence[MailMessage],
    *,
    now: datetime,
    contacts_by_address: Mapping[str, KnownContact],
    replied_thread_ids: AbstractSet[str],
    thread_tail_message_ids: AbstractSet[str],
    config: RankerConfig,
    contacts_by_message: Mapping[str, KnownContact] | None = None,
    debts_by_message: Mapping[str, "Debt"] | None = None,
) -> list[MailRankResult]:
    """Score every message and sort. Pure — the join results are handed in.

    `contacts_by_message` (message_id -> contact) wins over the sender lookup:
    it is how a thread's known contact, or a relay's counterparty, reaches a
    message whose own sender is unknown.
    """
    by_message = contacts_by_message or {}
    debts = debts_by_message or {}
    results = [
        score_message(
            message,
            now=now,
            contact=by_message.get(message.message_id)
            or contacts_by_address.get(normalize_address(message.from_addr)),
            debt=debts.get(message.message_id),
            replied_to_thread=message.thread_id in replied_thread_ids,
            is_thread_tail=message.message_id in thread_tail_message_ids,
            config=config,
        )
        for message in messages
    ]
    results.sort(key=_sort_key, reverse=True)
    return results


# --------------------------------------------------------------------------
# crown — exactly one thing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplyDraft:
    """Where a pre-drafted reply attaches. Nothing in this module fills it.

    The gap being closed is between knowing and starting, not between
    not-knowing and knowing, so the crowned item will eventually arrive with
    the reply already written. Writing it needs an LLM and is therefore a
    separate component — deliberately not built here. This type exists so that
    component has an obvious place to hand its output back, and so `crown()`'s
    shape does not have to change when it lands.
    """

    body: str
    generated_by: str
    generated_at: datetime


@dataclass(frozen=True)
class Displaced:
    """What the crown beat — as a count and one runner-up, never as a list.

    Returning the losers as a list would put the to-do list back on screen,
    which is the whole thing `crown()` exists to avoid. The count is here so
    the operator can see the crown is a choice rather than the only thing
    there is; the runner-up is here so "what else" has a one-line answer
    without becoming twelve.
    """

    count: int
    runner_up: MailRankResult | None = None

    def render(self) -> str:
        if self.count == 0:
            return "nothing else is above the line"
        plural = "item" if self.count == 1 else "items"
        if self.runner_up is None:
            return f"{self.count} other {plural} below it"
        return (
            f"{self.count} other {plural} below it — next up: "
            f"{self.runner_up.subject or '(no subject)'} "
            f"({self.runner_up.score})"
        )


@dataclass(frozen=True)
class Crown:
    """Exactly one thing to do, why it is that thing, and what it displaces.

    This is a hard requirement, not a UI preference. The constraint being
    designed against is executive dysfunction: a ranked list of twelve items is
    twelve more things to initiate, and a list of forty-seven overdue items
    produces avoidance — precisely the failure mode the loop exists to break.
    So the operator-facing shape returns one item or none. `surface()` stays
    for tests and review; nothing operator-facing should call it.

    A crown of `None` is a real answer. Nothing above the line means nothing
    above the line — a nag machine is a named risk in the PRD, and inventing a
    crown out of the least-irrelevant item would build one.
    """

    item: MailRankResult
    reason: str
    displaced: Displaced
    draft: ReplyDraft | None = None

    def with_draft(self, draft: ReplyDraft) -> "Crown":
        """Attach a reply drafted elsewhere. See `ReplyDraft`."""
        return replace(self, draft=draft)


def _crown_reason(result: MailRankResult) -> str:
    who = result.contact_name or normalize_address(result.from_addr) or "someone"
    subject = result.subject or "(no subject)"
    if result.is_owed_reply:
        days = int(round(result.age_days))
        plural = "day" if days == 1 else "days"
        return (
            f"You owe {who} a reply. \"{subject}\" has been sitting in your court "
            f"for {days} {plural} and nothing has happened in the thread since."
        )
    if result.age_days < 1.0:
        when = "today"
    else:
        when = f"{int(round(result.age_days))} days ago"
    return (
        f"{who} wrote {when} in a thread you are already in: \"{subject}\"."
    )


def crown(results: Sequence[MailRankResult]) -> Crown | None:
    """Pick one. Pure — `results` is already ranked by `rank_messages`."""
    surfaced = [result for result in results if result.surfaced]
    if not surfaced:
        return None
    top, rest = surfaced[0], surfaced[1:]
    return Crown(
        item=top,
        reason=_crown_reason(top),
        displaced=Displaced(count=len(rest), runner_up=rest[0] if rest else None),
    )


# --------------------------------------------------------------------------
# contact directory bindings
# --------------------------------------------------------------------------


class SqlAlchemyContactDirectory:
    """`ContactDirectory` over the `contacts` mirror of Dex (`ContactDB`)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def lookup(self, addresses: Sequence[str]) -> Mapping[str, KnownContact]:
        from .models import ContactDB

        wanted = sorted({normalize_address(a) for a in addresses} - {""})
        if not wanted:
            return {}
        rows = (
            self._db.query(ContactDB)
            .filter(func.lower(ContactDB.email).in_(wanted))
            .all()
        )
        found: dict[str, KnownContact] = {}
        for row in rows:
            key = normalize_address(row.email)
            if not key or key in found:
                continue
            found[key] = KnownContact(
                contact_id=str(row.id),
                name=row.name,
                email=key,
                relationship_tier=row.relationship_tier,
                organization_id=row.organization_id,
            )
        return found


@dataclass
class InMemoryContactDirectory:
    """Fixture-backed `ContactDirectory`."""

    contacts: Sequence[KnownContact] = ()

    def lookup(self, addresses: Sequence[str]) -> Mapping[str, KnownContact]:
        wanted = {normalize_address(a) for a in addresses} - {""}
        return {
            normalize_address(c.email): c
            for c in self.contacts
            if normalize_address(c.email) in wanted
        }


# --------------------------------------------------------------------------
# the binding
# --------------------------------------------------------------------------


class StupidRanker:
    """Binds the rule to the corpus and the contacts mirror.

    Two sweeps, because the two modes need different lookbacks. Arrivals live
    in a two-week window; an owed reply may be five months old and would never
    appear in it. The owed sweep therefore asks the corpus for thread *tails* —
    the newest message of each thread — over the horizon, and keeps only the
    ones that turn out to be owed. Everything else it pulls up is discarded
    rather than ranked, so the candidate set does not balloon with a year of
    dead mail.

    Nothing in this class decides relevance; it only fetches what the rule needs.
    """

    def __init__(
        self,
        *,
        corpus: MailCorpus,
        contacts: ContactDirectory,
        config: RankerConfig,
    ) -> None:
        self._corpus = corpus
        self._contacts = contacts
        self._config = config
        # Which reads came back exactly `limit` rows on the last `surface()`:
        # the window was cut by volume, not by time, and the caller should say so.
        self.last_read_truncated: tuple[str, ...] = ()

    def surface(
        self,
        *,
        now: datetime,
        window_days: int = DEFAULT_WINDOW_DAYS,
        limit: int = DEFAULT_FETCH_LIMIT,
        surfaced_only: bool = False,
    ) -> list[MailRankResult]:
        """The full ranked list. For tests and review — not operator-facing.

        Operator-facing surfaces call `crown()`.
        """
        # Without the operator's own addresses the reply signal can never fire,
        # owed mode can never trigger, and the operator's own sent mail can
        # never be gated — most of the rule silently dead. Fail closed, the way
        # `DeterministicIntentScorer` refuses to score against no Intent.
        if not self._config.owner_addresses:
            raise DomainRefusal("mail_owner_addresses_not_configured")

        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        arrivals = list(
            self._corpus.recent_messages(
                since=now - timedelta(days=window_days),
                until=now,
                limit=limit,
            )
        )
        tails = list(
            self._corpus.latest_messages_per_thread(
                since=now - timedelta(days=self._config.owed_horizon_days),
                until=now,
                limit=limit,
            )
        )
        tail_message_ids = frozenset(message.message_id for message in tails)
        self.last_read_truncated = tuple(
            name for name, rows in (("arrivals", arrivals), ("thread_tails", tails))
            if len(rows) >= limit
        )

        thread_ids = sorted(
            {m.thread_id for m in arrivals if m.thread_id}
            | {m.thread_id for m in tails if m.thread_id}
        )
        replied = self._corpus.threads_with_message_from(
            thread_ids,
            sorted(self._config.owner_addresses),
        )
        # Each inbound tail's own thread, whole: the arrival window (and its
        # row cap) is a view of what ARRIVED, and an owed thread's earlier
        # messages are exactly what a newest-first cap drops. Without them the
        # debt cannot be dated and a cc'd contact's name is never seen.
        inbound_threads = sorted({
            t.thread_id for t in tails
            if t.thread_id and normalize_address(t.from_addr) not in self._config.owner_addresses
        })
        history = list(self._corpus.thread_messages(inbound_threads)) if inbound_threads else []
        seen_ids: set[str] = set()
        everything: list[MailMessage] = []
        for m in arrivals + tails + history:
            if m.message_id not in seen_ids:
                seen_ids.add(m.message_id)
                everything.append(m)
        contacts_by_address = self._contacts.lookup(
            sorted({addr for m in everything
                    for addr in (m.from_addr, *m.to_addrs, *m.cc_addrs)}
                   - {""})
        )
        contacts_by_message = self._resolve_thread_contacts(everything, contacts_by_address)
        debts_by_message = self._resolve_debts(everything, tail_message_ids)

        seen = {message.message_id for message in arrivals}
        candidates = list(arrivals)
        for tail in tails:
            if tail.message_id in seen:
                continue
            sender = normalize_address(tail.from_addr)
            # The direction test, doing real work: a thread whose last word is
            # the operator's own is not a debt, whatever its age. The ball is
            # in their court and waiting is not a failure of his.
            is_inbound = sender not in self._config.owner_addresses
            debt = debts_by_message.get(tail.message_id)
            if not owes_a_reply(
                age_days=max(_age_days(tail.ts, now),
                             _age_days(debt.since, now) if debt else 0.0),
                contact=contacts_by_message.get(tail.message_id)
                or contacts_by_address.get(sender),
                is_thread_tail=True,
                is_inbound=is_inbound,
                config=self._config,
            ):
                continue
            candidates.append(tail)
            seen.add(tail.message_id)

        results = rank_messages(
            candidates,
            now=now,
            contacts_by_address=contacts_by_address,
            replied_thread_ids=replied,
            thread_tail_message_ids=tail_message_ids,
            config=self._config,
            contacts_by_message=contacts_by_message,
            debts_by_message=debts_by_message,
        )
        if surfaced_only:
            return [result for result in results if result.surfaced]
        return results

    def _resolve_debts(
        self,
        messages: Sequence[MailMessage],
        tail_message_ids: AbstractSet[str],
    ) -> dict[str, Debt]:
        """tail message_id -> when its thread's silence began.

        Walk back from the tail over the contiguous run of inbound messages;
        the run ends at the operator's last word. Bounded by what was fetched,
        so the debt is never dated earlier than the corpus can prove.
        """
        owners = self._config.owner_addresses
        by_thread: dict[str, list[MailMessage]] = {}
        for m in messages:
            by_thread.setdefault(m.thread_id, []).append(m)
        debts: dict[str, Debt] = {}
        for thread in by_thread.values():
            thread.sort(key=lambda m: (m.ts, m.message_id))
            tail = thread[-1]
            if tail.message_id not in tail_message_ids:
                continue
            run: list[MailMessage] = []
            for m in reversed(thread):
                if normalize_address(m.from_addr) in owners:
                    break
                run.append(m)
            if run:
                first = run[-1]
                debts[tail.message_id] = Debt(
                    since=first.ts, count=len(run),
                    started_by=normalize_address(first.from_addr),
                )
        return debts

    def _resolve_thread_contacts(
        self,
        messages: Sequence[MailMessage],
        contacts_by_address: Mapping[str, KnownContact],
    ) -> dict[str, KnownContact]:
        """message_id -> the contact the THREAD is with, when the sender is not one.

        The thread is with a known contact if, on the message itself, a known
        contact is in to/cc (the operator's own addresses excluded), or a known
        contact sent an earlier message in the same thread. Whose court the
        ball is in does not change with who typed last (2026-09-14: a colleague
        replying in a contact's thread demoted it from owed to stranger).

        A relay (`core.mail_relays`) resolves the same way: the counterparty is
        the contact, via the platform's direct message.
        """
        owners = self._config.owner_addresses
        by_thread: dict[str, list[MailMessage]] = {}
        for m in messages:
            by_thread.setdefault(m.thread_id, []).append(m)
        for thread in by_thread.values():
            thread.sort(key=lambda m: (m.ts, m.message_id))

        resolved: dict[str, KnownContact] = {}
        for m in messages:
            sender = normalize_address(m.from_addr)
            if sender in owners or sender in contacts_by_address:
                continue
            relay = relay_for(m)
            if relay is not None:
                resolved[m.message_id] = KnownContact(
                    contact_id=f"relay:{relay.channel}",
                    name=relay.counterparty,
                    email="",
                    via=f"{relay.channel} direct message",
                )
                continue
            found = None
            for role, addrs in (("cc", m.cc_addrs), ("to", m.to_addrs)):
                for raw in addrs:
                    addr = normalize_address(raw)
                    if addr in owners:
                        continue
                    contact = contacts_by_address.get(addr)
                    if contact is not None:
                        found = replace(contact, via=f"{role} '{addr}'")
                        break
                if found:
                    break
            if found is None:
                for earlier in by_thread.get(m.thread_id, ()):
                    if (earlier.ts, earlier.message_id) >= (m.ts, m.message_id):
                        break
                    contact = contacts_by_address.get(normalize_address(earlier.from_addr))
                    if contact is not None:
                        found = replace(contact, via=f"earlier in thread {m.thread_id}")
                        break
            if found is not None:
                resolved[m.message_id] = found
        return resolved

    def crown(
        self,
        *,
        now: datetime,
        window_days: int = DEFAULT_WINDOW_DAYS,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> Crown | None:
        """One thing, why, and what it displaces. `None` means nothing is due."""
        return crown(self.surface(now=now, window_days=window_days, limit=limit))
