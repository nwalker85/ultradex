"""Tests for the stupid ranker.

Fixtures only — nothing here touches vakr, Gmail, or a populated corpus.

Two acceptance cases live at the bottom, one per failure mode:

* `test_joe_dontz_...` — the mail that ARRIVED and was missed because its
  subject was ordinary.
* `test_google_recruiter_...` — the reply the operator OWED and never sent,
  missed for five months because nothing new ever happened in that thread.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.mail_reads import InMemoryMailCorpus, MailMessage, normalize_address
from core.mail_ranking import (
    MAX_ARRIVAL_SCORE,
    MAX_OWED_SCORE,
    MIN_OWED_SCORE,
    MODE_ARRIVAL,
    MODE_GATED,
    MODE_OWED_REPLY,
    Crown,
    InMemoryContactDirectory,
    KnownContact,
    RankerConfig,
    ReplyDraft,
    SqlAlchemyContactDirectory,
    StupidRanker,
    crown,
    owes_a_reply,
    rank_messages,
    score_message,
)


NOW = datetime(2026, 8, 25, 17, 0, tzinfo=timezone.utc)
OWNER = "nwalker85@gmail.com"


def _config(**overrides) -> RankerConfig:
    defaults = dict(owner_addresses=frozenset({OWNER}))
    defaults.update(overrides)
    return RankerConfig(**defaults)


def _message(**overrides) -> MailMessage:
    defaults = dict(
        message_id="msg-01",
        thread_id="thread-01",
        ts=NOW,
        from_addr="someone@example.com",
        from_name="Someone",
        to_addrs=(OWNER,),
        subject="Hello",
        labels=("INBOX",),
        snippet="",
    )
    defaults.update(overrides)
    return MailMessage(**defaults)


def _contact(**overrides) -> KnownContact:
    defaults = dict(
        contact_id="contact-01",
        name="Someone",
        email="someone@example.com",
        relationship_tier=None,
    )
    defaults.update(overrides)
    return KnownContact(**defaults)


def _score(message=None, **overrides):
    kwargs = dict(
        now=NOW,
        contact=_contact(),
        replied_to_thread=True,
        is_thread_tail=False,
        config=_config(),
    )
    kwargs.update(overrides)
    return score_message(message or _message(), **kwargs)


# --------------------------------------------------------------------------
# arrival mode — ball in their court
# --------------------------------------------------------------------------


def test_arrival_tops_out_at_the_arrival_ceiling():
    result = _score()

    assert result.mode == MODE_ARRIVAL
    assert result.score == MAX_ARRIVAL_SCORE == 70
    assert result.surfaced is True
    assert result.risk_flags == ()


def test_each_missing_arrival_signal_lowers_the_score_multiplicatively():
    all_three = _score().score
    no_reply = _score(replied_to_thread=False).score
    no_contact = _score(contact=None).score
    neither = _score(contact=None, replied_to_thread=False).score

    assert all_three > no_reply > no_contact > neither
    assert (all_three, no_reply, no_contact, neither) == (70, 38, 24, 13)


def test_arrival_recency_decays_by_half_life_and_never_reaches_zero():
    fresh = _score(_message(ts=NOW))
    one_half_life = _score(_message(ts=NOW - timedelta(days=7)))
    ancient = _score(_message(ts=NOW - timedelta(days=365 * 3)))

    assert fresh.score == 70
    assert one_half_life.score == 35
    # A three-year-old message (the corpus TTL) is ranked low, never gated out.
    assert ancient.score > 0
    assert ancient.surfaced is False


def test_missing_signals_are_floors_not_filters():
    """A stranger opening a cold thread still gets a score and an explanation.

    The design doc's objection to the deployed query is that it filters at
    ingest. A zero factor would reproduce that failure one layer down.
    """
    result = _score(contact=None, replied_to_thread=False)

    assert result.score > 0
    assert result.surfaced is False
    assert "is not in contacts" in result.explanation
    assert "never sent a message in thread" in result.explanation


def test_future_dated_message_does_not_score_above_the_ceiling():
    assert _score(_message(ts=NOW + timedelta(days=2))).score == MAX_ARRIVAL_SCORE


# --------------------------------------------------------------------------
# owed-reply mode — ball in HIS court, and it stayed there
# --------------------------------------------------------------------------


def test_owed_reply_requires_all_four_conditions():
    config = _config()
    base = dict(
        age_days=30.0,
        contact=_contact(),
        is_thread_tail=True,
        is_inbound=True,
        config=config,
    )

    assert owes_a_reply(**base) is True
    # Something newer happened in the thread — the ball moved back.
    assert owes_a_reply(**{**base, "is_thread_tail": False}) is False
    # A stranger's unanswered mail is not a reply you owe.
    assert owes_a_reply(**{**base, "contact": None}) is False
    # Inside the grace period it is just recent mail.
    assert owes_a_reply(**{**base, "age_days": 2.0}) is False
    # Past the horizon it is archaeology.
    assert owes_a_reply(**{**base, "age_days": 400.0}) is False


def test_a_thread_you_spoke_last_in_is_never_a_debt():
    """The direction test. Waiting on them is not a failure of his."""
    base = dict(
        age_days=300.0,
        contact=_contact(),
        is_thread_tail=True,
        config=_config(),
    )

    assert owes_a_reply(**base, is_inbound=True) is True
    assert owes_a_reply(**base, is_inbound=False) is False


def test_cold_open_from_a_known_contact_accrues_the_debt(db_session):
    """Operator ruling 2026-08-25: prior participation is NOT required.

    Two unanswered messages from the person who hired him at a previous
    company, two more from another contact — all cold opens, all missed. A
    ranker that required prior participation is structurally blind to exactly
    those, which is the failure mode being designed against.
    """
    from core.models import ContactDB

    db_session.add(
        ContactDB(
            id="contact-former-boss",
            name="Former Boss",
            email="former.boss@example.com",
            relationship_tier="champion",
        )
    )
    db_session.commit()

    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage(
                message_id="msg-cold-open",
                thread_id="thread-cold-open",
                ts=NOW - timedelta(days=7),
                from_addr="former.boss@example.com",
                to_addrs=(OWNER,),
                subject="Got a minute this week?",
                labels=("INBOX",),
            )
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=SqlAlchemyContactDirectory(db_session),
        config=_config(),
    )

    top = ranker.surface(now=NOW)[0]

    assert top.mode == MODE_OWED_REPLY
    assert top.score > MAX_ARRIVAL_SCORE
    assert "cold open — you have never replied in thread" in top.explanation
    assert "context, not a multiplier" in top.explanation
    assert "You owe Former Boss a reply" in ranker.crown(now=NOW).reason


def test_cold_open_from_an_UNKNOWN_sender_stays_in_arrival_mode():
    """The known-contact test is now the only thing standing between a debt and
    a recruiter blast, so it has to hold on its own.

    Identical shape to the test above — thread tail, inbound, well past the
    grace period, never replied to — differing only in that the sender is not
    in contacts. It must not become a 100-scoring obligation.
    """
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage(
                message_id="msg-ats-blast",
                thread_id="thread-ats",
                ts=NOW - timedelta(days=7),
                from_addr="careers@some-startup.example",
                to_addrs=(OWNER,),
                subject="Exciting opportunity for you",
                labels=("INBOX",),
            )
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=InMemoryContactDirectory(contacts=[]),
        config=_config(),
    )

    results = ranker.surface(now=NOW)

    assert [r.mode for r in results] == [MODE_ARRIVAL]
    assert results[0].score < MIN_OWED_SCORE
    assert results[0].surfaced is False
    assert ranker.crown(now=NOW) is None


def test_known_contact_matching_is_exact_address_not_domain(db_session):
    """A contact at parloa.com must not make every parloa.com address a debt."""
    from core.models import ContactDB

    db_session.add(
        ContactDB(id="c-joe", name="Joe Dontz", email="joe.dontz@parloa.com")
    )
    db_session.commit()

    found = SqlAlchemyContactDirectory(db_session).lookup(
        ["someone.else@parloa.com", "Joe Dontz <impostor@example.com>"]
    )

    assert found == {}


@pytest.mark.parametrize(
    "address",
    [
        "no-reply@greenhouse.io",
        "noreply@lever.co",
        "do-not-reply@myworkday.com",
        "notifications@linkedin.com",
        "mailer-daemon@example.com",
    ],
)
def test_an_unrepliable_address_can_never_accrue_a_debt(address):
    """Defence in depth for the day a mass sender lands in `contacts`.

    Owed mode only — an arrival from a no-reply address is still ranked, just
    low. You cannot owe a reply to something you cannot reply to.
    """
    contact = _contact(contact_id="c-blast", name="ATS Blast", email=address)

    assert (
        owes_a_reply(
            age_days=200.0,
            contact=contact,
            is_thread_tail=True,
            is_inbound=True,
            config=_config(),
        )
        is False
    )
    # ... but it is still scored as an arrival, not filtered out.
    arrival = _score(
        _message(from_addr=address, ts=NOW),
        contact=contact,
        is_thread_tail=True,
    )
    assert arrival.mode == MODE_ARRIVAL
    assert arrival.score > 0


def test_owed_reply_gets_LOUDER_with_age_which_is_the_inverse_of_recency():
    """Arrival decays with age; an owed reply must do the opposite.

    Reusing `0.5 ** (age/7)` here is precisely how the Google thread was
    missed: at five months it scores ~0 as an arrival.
    """
    ages = [4, 10, 30, 60, 90]
    owed_scores = [
        _score(
            _message(ts=NOW - timedelta(days=age), thread_id="t"),
            is_thread_tail=True,
        ).score
        for age in ages
    ]
    arrival_scores = [
        _score(_message(ts=NOW - timedelta(days=age)), is_thread_tail=False).score
        for age in ages
    ]

    assert owed_scores == sorted(owed_scores), "owed reply must rise with age"
    assert arrival_scores == sorted(arrival_scores, reverse=True), "arrival must decay"
    assert owed_scores == [72, 74, 81, 90, 100]


def test_owed_reply_saturates_and_then_stops_counting_past_the_horizon():
    saturated = _score(_message(ts=NOW - timedelta(days=90)), is_thread_tail=True)
    five_months = _score(_message(ts=NOW - timedelta(days=152)), is_thread_tail=True)
    two_years = _score(_message(ts=NOW - timedelta(days=730)), is_thread_tail=True)

    # Plateau: more silence past saturation does not make it louder.
    assert saturated.score == five_months.score == MAX_OWED_SCORE == 100
    # Horizon: past a year it is archaeology, not an obligation. It falls back
    # to arrival scoring and stops owning the crown.
    assert two_years.mode == MODE_ARRIVAL
    assert two_years.surfaced is False
    assert two_years.score < MIN_OWED_SCORE


def test_any_owed_reply_outranks_anything_that_merely_arrived_today():
    best_possible_arrival = _score()
    weakest_possible_owed = _score(
        _message(ts=NOW - timedelta(days=3.01)), is_thread_tail=True
    )

    assert best_possible_arrival.score == MAX_ARRIVAL_SCORE
    assert weakest_possible_owed.mode == MODE_OWED_REPLY
    assert weakest_possible_owed.score >= MIN_OWED_SCORE
    assert weakest_possible_owed.score > best_possible_arrival.score
    # The bands do not overlap. That gap is the design.
    assert MIN_OWED_SCORE > MAX_ARRIVAL_SCORE


def test_owed_explanation_names_the_factor_the_age_and_the_preconditions():
    result = _score(
        _message(ts=NOW - timedelta(days=45), thread_id="thread-x"),
        contact=_contact(name="Joe Dontz", relationship_tier="hiring_manager"),
        is_thread_tail=True,
    )

    assert [f.label for f in result.factors] == [
        "owed_reply",
        "known_contact",
        "thread_history",
    ]
    assert "unanswered for 45.0 days" in result.explanation
    assert "grace 3d, saturates at 90d" in result.explanation
    assert "tier=hiring_manager" in result.explanation
    assert "precondition of owed mode" in result.explanation
    assert "you have sent a message in thread thread-x before" in result.explanation
    assert "context, not a multiplier" in result.explanation
    assert result.explanation.endswith(f"= {result.score}")
    assert result.risk_flags == ("owed_reply",)
    assert len(result.explanation) <= 1000


# --------------------------------------------------------------------------
# hard gates
# --------------------------------------------------------------------------


def test_own_sent_mail_is_gated_to_zero():
    result = _score(_message(from_addr=f"Nate Walker <{OWNER.upper()}>"))

    assert result.score == 0
    assert result.mode == MODE_GATED
    assert result.surfaced is False
    assert result.risk_flags == ("own_message",)
    assert "you sent this message" in result.explanation


@pytest.mark.parametrize("label", ["SPAM", "TRASH", "DRAFT"])
def test_already_decided_labels_are_gated_to_zero(label):
    result = _score(_message(labels=("INBOX", label)), is_thread_tail=True)

    assert result.score == 0
    assert result.mode == MODE_GATED
    assert result.risk_flags == ("label_suppressed",)
    assert label in result.explanation


# --------------------------------------------------------------------------
# explainability
# --------------------------------------------------------------------------


def test_arrival_explanation_names_every_factor_and_the_arithmetic():
    result = _score(contact=_contact(name="Joe Dontz", relationship_tier="hiring_manager"))

    assert [f.label for f in result.factors] == [
        "recency",
        "known_contact",
        "replied_thread",
    ]
    for fragment in ("recency", "known_contact", "replied_thread", "half-life"):
        assert fragment in result.explanation
    assert "tier=hiring_manager" in result.explanation
    assert result.explanation.endswith("= 70")


def test_absent_arrival_signals_are_reported_as_risk_flags():
    result = _score(contact=None, replied_to_thread=False)

    assert set(result.risk_flags) == {"known_contact_absent", "replied_thread_absent"}


# --------------------------------------------------------------------------
# ordering
# --------------------------------------------------------------------------


def test_ranking_is_deterministic_and_sorted_by_score_then_recency():
    messages = [
        _message(message_id="cold", thread_id="t-cold", from_addr="cold@example.com"),
        _message(message_id="warm", thread_id="t-warm", from_addr="someone@example.com"),
        _message(
            message_id="old-warm",
            thread_id="t-warm-old",
            from_addr="someone@example.com",
            ts=NOW - timedelta(days=5),
        ),
    ]
    kwargs = dict(
        now=NOW,
        contacts_by_address={"someone@example.com": _contact()},
        replied_thread_ids={"t-warm", "t-warm-old"},
        thread_tail_message_ids=frozenset(),
        config=_config(),
    )

    ordered = rank_messages(messages, **kwargs)

    assert [r.message_id for r in ordered] == ["warm", "old-warm", "cold"]
    assert [r.message_id for r in rank_messages(list(reversed(messages)), **kwargs)] == [
        r.message_id for r in ordered
    ]


def test_owed_ties_break_toward_the_MORE_overdue_not_the_more_recent():
    """Both saturated at 100; the older one is the one still rotting."""
    older = _message(
        message_id="older", thread_id="t-older", ts=NOW - timedelta(days=200)
    )
    newer = _message(
        message_id="newer", thread_id="t-newer", ts=NOW - timedelta(days=120)
    )

    ordered = rank_messages(
        [newer, older],
        now=NOW,
        contacts_by_address={"someone@example.com": _contact()},
        replied_thread_ids={"t-older", "t-newer"},
        thread_tail_message_ids=frozenset({"older", "newer"}),
        config=_config(),
    )

    assert [r.score for r in ordered] == [100, 100]
    assert [r.message_id for r in ordered] == ["older", "newer"]


# --------------------------------------------------------------------------
# crown — exactly one thing
# --------------------------------------------------------------------------


def test_crown_returns_exactly_one_item_and_what_it_displaces():
    results = rank_messages(
        [
            _message(message_id=f"m{i}", thread_id=f"t{i}", subject=f"Subject {i}")
            for i in range(5)
        ],
        now=NOW,
        contacts_by_address={"someone@example.com": _contact()},
        replied_thread_ids={f"t{i}" for i in range(5)},
        thread_tail_message_ids=frozenset(),
        config=_config(),
    )

    result = crown(results)

    assert isinstance(result, Crown)
    assert result.item.score == 70
    assert result.displaced.count == 4
    assert result.displaced.runner_up is not None
    assert "4 other items below it" in result.displaced.render()
    # The losers are a count and one runner-up, never a list to work through.
    assert not hasattr(result.displaced, "items")


def test_crown_is_none_when_nothing_is_above_the_line():
    """Silence is a real answer. Inventing a crown would build the nag machine."""
    results = rank_messages(
        [_message(from_addr="stranger@example.com", ts=NOW - timedelta(days=20))],
        now=NOW,
        contacts_by_address={},
        replied_thread_ids=set(),
        thread_tail_message_ids=frozenset(),
        config=_config(),
    )

    assert all(not r.surfaced for r in results)
    assert crown(results) is None


def test_crown_reason_is_a_sentence_not_a_score_dump():
    owed = crown(
        rank_messages(
            [_message(ts=NOW - timedelta(days=40), subject="Availability?")],
            now=NOW,
            contacts_by_address={"someone@example.com": _contact(name="Dana Reeve")},
            replied_thread_ids={"thread-01"},
            thread_tail_message_ids=frozenset({"msg-01"}),
            config=_config(),
        )
    )
    arrived = crown(
        rank_messages(
            [_message(subject="Availability?")],
            now=NOW,
            contacts_by_address={"someone@example.com": _contact(name="Dana Reeve")},
            replied_thread_ids={"thread-01"},
            thread_tail_message_ids=frozenset(),
            config=_config(),
        )
    )

    assert "You owe Dana Reeve a reply" in owed.reason
    assert "40 days" in owed.reason
    assert "Availability?" in owed.reason

    assert "Dana Reeve wrote today" in arrived.reason
    assert "You owe" not in arrived.reason


def test_crown_has_an_empty_slot_for_a_draft_this_module_never_fills():
    """The draft needs an LLM and is a separate component. Only the slot is here."""
    result = crown(
        rank_messages(
            [_message()],
            now=NOW,
            contacts_by_address={"someone@example.com": _contact()},
            replied_thread_ids={"thread-01"},
            thread_tail_message_ids=frozenset(),
            config=_config(),
        )
    )

    assert result.draft is None

    drafted = result.with_draft(
        ReplyDraft(body="Hi — sorry for the delay.", generated_by="elsewhere", generated_at=NOW)
    )
    assert drafted.draft.body == "Hi — sorry for the delay."
    assert drafted.item is result.item
    assert result.draft is None, "with_draft must not mutate the original crown"


def test_ranker_crown_is_the_operator_facing_shape():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("me", "t1", NOW - timedelta(days=200), OWNER, labels=("SENT",)),
            MailMessage(
                "owed",
                "t1",
                NOW - timedelta(days=150),
                "someone@example.com",
                subject="Still interested?",
                labels=("INBOX",),
            ),
            MailMessage(
                "today", "t2", NOW, "someone@example.com", subject="FYI", labels=("INBOX",)
            ),
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=InMemoryContactDirectory(contacts=[_contact()]),
        config=_config(),
    )

    result = ranker.crown(now=NOW)

    assert result.item.message_id == "owed"
    assert result.item.mode == MODE_OWED_REPLY
    assert result.displaced.count == 1


# --------------------------------------------------------------------------
# the joins, wired
# --------------------------------------------------------------------------


def test_reply_detection_uses_owner_sent_messages_anywhere_in_the_thread():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage(
                message_id="them-2",
                thread_id="thread-A",
                ts=NOW,
                from_addr="someone@example.com",
                subject="Re: something",
                labels=("INBOX",),
            ),
            MailMessage(
                message_id="me-1",
                thread_id="thread-A",
                ts=NOW - timedelta(days=1),
                from_addr=OWNER,
                subject="something",
                labels=("SENT",),
            ),
            MailMessage(
                message_id="them-cold",
                thread_id="thread-B",
                ts=NOW,
                from_addr="someone@example.com",
                subject="cold open",
                labels=("INBOX",),
            ),
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=InMemoryContactDirectory(contacts=[_contact()]),
        config=_config(),
    )

    results = {r.message_id: r for r in ranker.surface(now=NOW)}

    assert results["them-2"].score == 70
    assert results["them-cold"].score == 38
    # The operator's own message in the thread is gated, not ranked.
    assert results["me-1"].score == 0
    assert results["me-1"].risk_flags == ("own_message",)


def test_owed_sweep_reaches_past_the_arrival_window():
    """A five-month-old owed reply is invisible to a two-week arrival window."""
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("me", "t1", NOW - timedelta(days=160), OWNER, labels=("SENT",)),
            MailMessage(
                "owed",
                "t1",
                NOW - timedelta(days=150),
                "someone@example.com",
                labels=("INBOX",),
            ),
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=InMemoryContactDirectory(contacts=[_contact()]),
        config=_config(),
    )

    results = ranker.surface(now=NOW, window_days=14)

    assert [r.message_id for r in results if r.surfaced] == ["owed"]
    assert results[0].mode == MODE_OWED_REPLY


def test_owed_sweep_discards_thread_tails_that_are_not_owed():
    """The long lookback must not balloon the candidate set with dead mail.

    Two shapes that reach the sweep and must be dropped: a stranger's old
    unanswered mail, and a thread where the operator himself had the last word.
    (A known contact's cold open is NOT in this list — since the 2026-08-25
    ruling that is a debt, and it has its own test.)
    """
    corpus = InMemoryMailCorpus(
        messages=[
            # Old, operator replied, but the sender is a stranger.
            MailMessage("me", "t-str", NOW - timedelta(days=110), OWNER, labels=("SENT",)),
            MailMessage(
                "stranger-old",
                "t-str",
                NOW - timedelta(days=100),
                "stranger@example.com",
                labels=("INBOX",),
            ),
            # Old, known contact, but the operator had the last word.
            MailMessage(
                "them",
                "t-mine",
                NOW - timedelta(days=120),
                "someone@example.com",
                labels=("INBOX",),
            ),
            MailMessage(
                "me-last", "t-mine", NOW - timedelta(days=100), OWNER, labels=("SENT",)
            ),
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=InMemoryContactDirectory(contacts=[_contact()]),
        config=_config(),
    )

    assert ranker.surface(now=NOW) == []
    assert ranker.crown(now=NOW) is None


def test_surfaced_only_applies_the_threshold():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("hot", "thread-A", NOW, "someone@example.com", labels=("INBOX",)),
            MailMessage(
                "cold",
                "thread-B",
                NOW - timedelta(days=10),
                "stranger@example.com",
                labels=("INBOX",),
            ),
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=InMemoryContactDirectory(contacts=[_contact()]),
        config=_config(),
    )

    assert [r.message_id for r in ranker.surface(now=NOW, surfaced_only=True)] == ["hot"]
    assert len(ranker.surface(now=NOW)) == 2


def test_sweep_refuses_when_the_operator_has_no_configured_addresses():
    """Without owner addresses the reply and owed signals are structurally dead."""
    from core.jobsearch_executors import DomainRefusal

    ranker = StupidRanker(
        corpus=InMemoryMailCorpus(messages=[_message()]),
        contacts=InMemoryContactDirectory(contacts=[_contact()]),
        config=RankerConfig(owner_addresses=frozenset()),
    )

    with pytest.raises(DomainRefusal) as excinfo:
        ranker.surface(now=NOW)

    assert "mail_owner_addresses_not_configured" in str(excinfo.value)


def test_config_from_env_reads_owner_addresses_and_knobs():
    config = RankerConfig.from_env(
        {
            "MAIL_OWNER_ADDRESSES": f"{OWNER}, Nate <nate@ravenhelm.dev> ,",
            "MAIL_RANKER_HALF_LIFE_DAYS": "3",
            "MAIL_RANKER_SURFACE_THRESHOLD": "55",
            "MAIL_RANKER_OWED_HORIZON_DAYS": "180",
        }
    )

    assert config.owner_addresses == frozenset({OWNER, "nate@ravenhelm.dev"})
    assert config.recency_half_life_days == 3.0
    assert config.surface_threshold == 55
    assert config.owed_horizon_days == 180.0
    assert RankerConfig.from_env({}).owner_addresses == frozenset()


def test_config_rejects_an_incoherent_owed_band():
    with pytest.raises(ValueError):
        RankerConfig(owed_grace_days=100.0, owed_saturation_days=90.0)
    with pytest.raises(ValueError):
        RankerConfig(owed_saturation_days=90.0, owed_horizon_days=30.0)


def test_window_bounds_the_arrival_sweep():
    corpus = InMemoryMailCorpus(
        messages=[
            MailMessage("inside", "t1", NOW - timedelta(days=3), "someone@example.com"),
            # A stranger, so the owed sweep discards it and only the arrival
            # window decides whether it appears.
            MailMessage("outside", "t2", NOW - timedelta(days=30), "stranger@example.com"),
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=InMemoryContactDirectory(contacts=[_contact()]),
        config=_config(),
    )

    assert [r.message_id for r in ranker.surface(now=NOW, window_days=14)] == ["inside"]


# --------------------------------------------------------------------------
# contacts join against the real `contacts` mirror of Dex
# --------------------------------------------------------------------------


def test_contact_directory_matches_contacts_table_case_insensitively(db_session):
    from core.models import ContactDB

    db_session.add(
        ContactDB(
            id="contact-joe",
            name="Joe Dontz",
            email="Joe.Dontz@Parloa.com",
            company="Parloa",
            job_title="Hiring Manager",
            relationship_tier="hiring_manager",
        )
    )
    db_session.commit()

    found = SqlAlchemyContactDirectory(db_session).lookup(
        ["Joe Dontz <joe.dontz@parloa.com>", "nobody@example.com"]
    )

    assert set(found) == {"joe.dontz@parloa.com"}
    assert found["joe.dontz@parloa.com"].name == "Joe Dontz"
    assert found["joe.dontz@parloa.com"].relationship_tier == "hiring_manager"


def test_contact_directory_ignores_contacts_without_an_email(db_session):
    from core.models import ContactDB

    db_session.add(ContactDB(id="contact-noemail", name="No Email", email=None))
    db_session.commit()

    assert SqlAlchemyContactDirectory(db_session).lookup(["someone@example.com"]) == {}


def test_normalize_address_unwraps_display_names():
    assert normalize_address("Joe Dontz <Joe.Dontz@Parloa.com>") == "joe.dontz@parloa.com"
    assert normalize_address("  JOE@parloa.com ") == "joe@parloa.com"
    assert normalize_address(None) == ""


# ==========================================================================
# ACCEPTANCE 1 — the mail that ARRIVED and the deployed sweep query missed
# ==========================================================================


def test_joe_dontz_hiring_manager_mail_surfaces_where_the_gmail_query_missed_it(
    db_session,
):
    """2026-08-25: the hiring manager's actual mail, ranked.

    `DEFAULT_GMAIL_SENSE_QUERY` did not match it — `parloa.com` is not an ATS
    domain and "Re: Follow-up — links, tenant access, and scheduling the demo"
    contains none of the six subject phrases. The dumb rule catches it on
    signals the subject line never carried: Joe is a known contact, Nate had
    already replied in that thread, and it arrived today.

    The test asserts the *reason*, not only the rank. If a future change makes
    this pass for some other reason, that is a regression.
    """
    from core.models import ContactDB

    db_session.add(
        ContactDB(
            id="contact-joe-dontz",
            name="Joe Dontz",
            email="joe.dontz@parloa.com",
            company="Parloa",
            job_title="Hiring Manager",
            relationship_tier="hiring_manager",
        )
    )
    db_session.commit()

    corpus = InMemoryMailCorpus(
        messages=[
            # The mail that was missed.
            MailMessage(
                message_id="msg-joe-followup",
                thread_id="thread-parloa-followup",
                ts=NOW,
                from_addr="Joe Dontz <joe.dontz@parloa.com>",
                from_name="Joe Dontz",
                to_addrs=(OWNER,),
                subject="Re: Follow-up — links, tenant access, and scheduling the demo",
                labels=("INBOX", "UNREAD"),
                snippet="Thanks Nate — here are the links and tenant details.",
            ),
            # Nate's earlier reply in the same thread: the reply signal.
            MailMessage(
                message_id="msg-nate-reply",
                thread_id="thread-parloa-followup",
                ts=NOW - timedelta(days=1),
                from_addr=OWNER,
                to_addrs=("joe.dontz@parloa.com",),
                subject="Follow-up — links, tenant access, and scheduling the demo",
                labels=("SENT",),
            ),
            # An ATS blast the old query *would* have matched — same day,
            # unknown sender, no reply. It must not outrank Joe.
            MailMessage(
                message_id="msg-ats-blast",
                thread_id="thread-ats",
                ts=NOW,
                from_addr="no-reply@greenhouse.io",
                to_addrs=(OWNER,),
                subject="Thank you for applying",
                labels=("INBOX",),
            ),
        ]
    )

    ranker = StupidRanker(
        corpus=corpus,
        contacts=SqlAlchemyContactDirectory(db_session),
        config=_config(),
    )

    ranked = ranker.surface(now=NOW)
    top = ranked[0]

    assert top.message_id == "msg-joe-followup"
    assert top.mode == MODE_ARRIVAL
    assert top.score == MAX_ARRIVAL_SCORE
    assert top.surfaced is True
    assert top.contact_id == "contact-joe-dontz"
    assert top.risk_flags == ()

    # It surfaced for the three stated reasons, and says so.
    assert {f.label: f.value for f in top.factors} == {
        "recency": 1.0,
        "known_contact": 1.0,
        "replied_thread": 1.0,
    }
    assert "is contact 'Joe Dontz'" in top.explanation
    assert "tier=hiring_manager" in top.explanation
    assert "you have sent a message in thread thread-parloa-followup" in top.explanation

    # The mail the frozen query *did* match ranks well below it.
    ats = next(r for r in ranked if r.message_id == "msg-ats-blast")
    assert ats.score < top.score
    assert ats.surfaced is False

    # And the operator is handed one thing, not three.
    result = ranker.crown(now=NOW)
    assert result.item.message_id == "msg-joe-followup"
    assert "Joe Dontz wrote today" in result.reason
    assert result.displaced.count == 0


# ==========================================================================
# ACCEPTANCE 2 — the reply he OWED and never sent
# ==========================================================================


def test_google_recruiter_owed_reply_surfaces_after_five_months_of_silence(db_session):
    """2026-03-06: a Google Cloud Sourcing recruiter advanced Nate to interview
    scheduling and asked for his availability. He never replied. The role died.

    Five months outstanding and nothing in the system ever said so, because
    nothing about that thread was ever *new*. An arrival-only ranker scores it
    at ~1 out of 70; the owed-reply mode scores it 100 and crowns it over mail
    that arrived today.

    The fixture also carries a two-year-dead thread with identical structure,
    to prove the horizon: it must not dominate, or the crown becomes a
    permanent monument to the oldest thing in the mailbox.
    """
    from core.models import ContactDB

    db_session.add_all(
        [
            ContactDB(
                id="contact-google-sourcing",
                name="Google Cloud Sourcing",
                email="cloud-sourcing@google.com",
                company="Google",
                job_title="Technical Recruiter",
                relationship_tier="recruiter",
            ),
            ContactDB(
                id="contact-joe-dontz",
                name="Joe Dontz",
                email="joe.dontz@parloa.com",
                company="Parloa",
                relationship_tier="hiring_manager",
            ),
            ContactDB(
                id="contact-ancient",
                name="Ancient Thread",
                email="ancient@example.com",
                relationship_tier="peer",
            ),
        ]
    )
    db_session.commit()

    recruiter_ts = datetime(2026, 3, 6, 15, 30, tzinfo=timezone.utc)
    corpus = InMemoryMailCorpus(
        messages=[
            # Nate's reply earlier in the thread — he participated, then stopped.
            MailMessage(
                message_id="msg-nate-google",
                thread_id="thread-google-cloud-sourcing",
                ts=recruiter_ts - timedelta(days=2),
                from_addr=OWNER,
                to_addrs=("cloud-sourcing@google.com",),
                subject="Re: Google Cloud — Solutions Architect",
                labels=("SENT",),
            ),
            # The message he owes a reply to. Nothing has happened since.
            MailMessage(
                message_id="msg-google-recruiter",
                thread_id="thread-google-cloud-sourcing",
                ts=recruiter_ts,
                from_addr="Google Cloud Sourcing <cloud-sourcing@google.com>",
                from_name="Google Cloud Sourcing",
                to_addrs=(OWNER,),
                subject="Re: Google Cloud — Solutions Architect: interview scheduling",
                labels=("INBOX",),
                snippet="Could you share your availability for next week?",
            ),
            # Today's mail from the hiring manager: the best an arrival can be.
            MailMessage(
                message_id="msg-nate-parloa",
                thread_id="thread-parloa",
                ts=NOW - timedelta(days=1),
                from_addr=OWNER,
                labels=("SENT",),
            ),
            MailMessage(
                message_id="msg-joe-today",
                thread_id="thread-parloa",
                ts=NOW,
                from_addr="joe.dontz@parloa.com",
                to_addrs=(OWNER,),
                subject="Re: Follow-up — links, tenant access, and scheduling the demo",
                labels=("INBOX",),
            ),
            # A two-year-dead thread with the same shape. Must not dominate.
            MailMessage(
                message_id="msg-nate-ancient",
                thread_id="thread-ancient",
                ts=NOW - timedelta(days=740),
                from_addr=OWNER,
                labels=("SENT",),
            ),
            MailMessage(
                message_id="msg-ancient",
                thread_id="thread-ancient",
                ts=NOW - timedelta(days=730),
                from_addr="ancient@example.com",
                to_addrs=(OWNER,),
                subject="Coffee sometime?",
                labels=("INBOX",),
            ),
        ]
    )

    ranker = StupidRanker(
        corpus=corpus,
        contacts=SqlAlchemyContactDirectory(db_session),
        config=_config(),
    )

    ranked = ranker.surface(now=NOW)
    top = ranked[0]

    # It surfaces, at the top, five months late.
    assert top.message_id == "msg-google-recruiter"
    assert top.mode == MODE_OWED_REPLY
    assert top.score == MAX_OWED_SCORE == 100
    assert top.surfaced is True
    assert top.contact_id == "contact-google-sourcing"
    assert 170 < top.age_days < 175  # five months

    # The explanation names the owed-reply factor and the age.
    assert [f.label for f in top.factors][0] == "owed_reply"
    assert f"unanswered for {top.age_days:.1f} days" in top.explanation
    assert "is inbound and unanswered" in top.explanation
    assert "is contact 'Google Cloud Sourcing', tier=recruiter" in top.explanation
    assert "score = 72 + 28 x 1.00 = 100" in top.explanation

    # It outranks the best thing that merely arrived today.
    joe = next(r for r in ranked if r.message_id == "msg-joe-today")
    assert joe.mode == MODE_ARRIVAL
    assert joe.score == MAX_ARRIVAL_SCORE
    assert top.score > joe.score

    # The two-year-dead thread does not dominate — past the horizon it is not
    # an obligation at all, and never reaches the candidate set.
    assert "msg-ancient" not in {r.message_id for r in ranked}

    # The debt does not rest on the prior reply that happens to be in this
    # fixture: strip it and the score is identical (ruling, 2026-08-25).
    without_history = StupidRanker(
        corpus=InMemoryMailCorpus(
            messages=[
                m for m in corpus.messages if m.message_id != "msg-nate-google"
            ]
        ),
        contacts=SqlAlchemyContactDirectory(db_session),
        config=_config(),
    ).surface(now=NOW)[0]
    assert without_history.message_id == "msg-google-recruiter"
    assert without_history.score == MAX_OWED_SCORE
    assert "cold open" in without_history.explanation

    # The operator is handed one thing, with a reason and what it displaced.
    result = ranker.crown(now=NOW)
    assert result.item.message_id == "msg-google-recruiter"
    assert "You owe Google Cloud Sourcing a reply" in result.reason
    assert f"{int(round(top.age_days))} days" in result.reason
    assert "nothing has happened in the thread since" in result.reason
    assert result.displaced.count == 1
    assert result.displaced.runner_up.message_id == "msg-joe-today"
    assert result.draft is None  # the draft is a separate component


# ==========================================================================
# ACCEPTANCE 3 — the cold opens from known contacts, never answered
# ==========================================================================


def test_unanswered_cold_opens_from_known_contacts_accrue_debt(db_session):
    """The shape the participation condition used to be blind to.

    Two messages from the person who hired Nate at a previous company
    (2026-08-18, 2026-08-19) and two from another contact (2026-08-14,
    2026-08-21), all unanswered, none in a thread he had ever spoken in. Under
    the original rule none of them could ever accrue owed-reply debt; under the
    2026-08-25 ruling every one of them does.

    The real instances arrived as LinkedIn DMs, which do not live in
    `mail.messages` at all — this models the same shape as it appears in mail,
    sent from each contact's own address.
    """
    from core.models import ContactDB

    db_session.add_all(
        [
            ContactDB(
                id="contact-former-boss",
                name="Former Boss",
                email="former.boss@example.com",
                relationship_tier="champion",
            ),
            ContactDB(
                id="contact-peer",
                name="Old Colleague",
                email="old.colleague@example.com",
                relationship_tier="peer",
            ),
        ]
    )
    db_session.commit()

    def _inbound(mid, thread, day, addr, subject):
        return MailMessage(
            message_id=mid,
            thread_id=thread,
            ts=datetime(2026, 8, day, 9, 0, tzinfo=timezone.utc),
            from_addr=addr,
            to_addrs=(OWNER,),
            subject=subject,
            labels=("INBOX",),
        )

    corpus = InMemoryMailCorpus(
        messages=[
            _inbound("boss-1", "thread-boss", 18, "former.boss@example.com", "Hey!"),
            _inbound("boss-2", "thread-boss", 19, "former.boss@example.com", "Re: Hey!"),
            _inbound(
                "peer-1", "thread-peer", 14, "old.colleague@example.com", "Catch up?"
            ),
            _inbound(
                "peer-2", "thread-peer", 21, "old.colleague@example.com", "Re: Catch up?"
            ),
        ]
    )
    ranker = StupidRanker(
        corpus=corpus,
        contacts=SqlAlchemyContactDirectory(db_session),
        config=_config(),
    )

    ranked = ranker.surface(now=NOW)
    owed = [r for r in ranked if r.is_owed_reply]

    # Only each thread's LAST word carries the debt — not every message in it.
    assert [r.message_id for r in owed] == ["boss-2", "peer-2"]
    assert all(r.score >= MIN_OWED_SCORE for r in owed)
    assert all("cold open — you have never replied" in r.explanation for r in owed)

    # The older silence is the louder one.
    assert owed[0].message_id == "boss-2"
    assert owed[0].score > owed[1].score

    # The earlier messages in each thread are still ranked, as arrivals, and
    # never as a second copy of the same debt.
    earlier = {r.message_id: r for r in ranked if r.message_id in {"boss-1", "peer-1"}}
    assert earlier["boss-1"].mode == MODE_ARRIVAL
    assert earlier["boss-1"].score < MIN_OWED_SCORE

    # One thing, not four. `displaced` counts only what was above the line —
    # the two earlier messages score below the threshold as stale arrivals, so
    # the operator is told about one debt and one alternative, not a backlog.
    result = ranker.crown(now=NOW)
    assert result.item.message_id == "boss-2"
    assert "You owe Former Boss a reply" in result.reason
    assert result.displaced.count == 1
    assert result.displaced.runner_up.message_id == "peer-2"
    assert [r.message_id for r in ranker.surface(now=NOW, surfaced_only=True)] == [
        "boss-2",
        "peer-2",
    ]
