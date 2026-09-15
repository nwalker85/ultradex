from datetime import datetime, timedelta, timezone

from core.mail_ranking import MODE_ARRIVAL, MODE_OWED_REPLY, MailRankResult
from core.mail_reads import MailMessage
from core.owed_replies import (
    CccContactDirectory,
    ContactRow,
    ObservingCorpus,
    UnionCorpus,
    looks_like_bulk_sender,
    normalize_name,
    person_shaped,
    plan_sync,
    task_id_for,
    task_payload,
)

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

ROWS = [
    ContactRow(id="c-michelle", name="Michelle Foster Earle", email=None, company="OmniSure"),
    ContactRow(id="c-wesley", name="Wesley Earle, AINS", email=None, job_title="Underwriter"),
    ContactRow(id="c-aayush", name="Aayush Mediratta", email="aayush@jaggaer.com", company="JAGGAER"),
]


def _result(**overrides) -> MailRankResult:
    base = dict(
        message_id="m1",
        thread_id="t1",
        ts=NOW - timedelta(days=7),
        from_addr="michelle@omnisure.com",
        subject="Re: independent verification",
        score=95,
        surfaced=True,
        explanation="owed reply: known contact, thread tail, 7d",
        mode=MODE_OWED_REPLY,
        age_days=7.0,
    )
    base.update(overrides)
    return MailRankResult(**base)


def _message(**overrides) -> MailMessage:
    base = dict(message_id="m1", thread_id="t1", ts=NOW, from_addr="michelle@omnisure.com", from_name="Michelle Earle")
    base.update(overrides)
    return MailMessage(**base)


# --- names -----------------------------------------------------------------


def test_normalize_name_drops_case_punctuation_and_credential_suffixes():
    assert normalize_name("Wesley Earle, AINS") == "wesley earle"
    assert normalize_name("  Michèle  FOSTER-Earle ") == "michele foster earle"
    assert normalize_name(None) == ""


# --- directory -------------------------------------------------------------


def test_email_match_wins_when_the_mirror_has_an_address():
    directory = CccContactDirectory.from_rows(ROWS)
    found = directory.lookup(["Aayush <AAYUSH@jaggaer.com>"])
    assert found["aayush@jaggaer.com"].contact_id == "c-aayush"
    assert directory.matched_by["aayush@jaggaer.com"] == "email"


def test_display_name_fallback_matches_first_and_last_against_a_three_part_name():
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message(from_name="Michelle Earle")])
    found = directory.lookup(["michelle@omnisure.com"])
    assert found["michelle@omnisure.com"].contact_id == "c-michelle"
    assert directory.matched_by["michelle@omnisure.com"] == "name"
    assert directory.company_for(found["michelle@omnisure.com"]) == "OmniSure"


def test_unknown_sender_with_no_display_name_is_not_a_contact():
    directory = CccContactDirectory.from_rows(ROWS)
    assert directory.lookup(["nobody@example.com"]) == {}


def test_observing_corpus_registers_display_names_from_every_read():
    class Corpus:
        def recent_messages(self, **kw):
            return [_message(message_id="a", from_name="Wesley Earle")]

        def latest_messages_per_thread(self, **kw):
            return [_message(message_id="b", from_addr="w2@example.com", from_name="Wesley Earle")]

        def threads_with_message_from(self, thread_ids, addresses):
            return set()

    directory = CccContactDirectory.from_rows(ROWS)
    corpus = ObservingCorpus(Corpus(), directory)
    corpus.recent_messages(since=NOW, until=NOW)
    corpus.latest_messages_per_thread(since=NOW, until=NOW)
    assert directory.display_names == {"michelle@omnisure.com": "Wesley Earle", "w2@example.com": "Wesley Earle"}
    assert directory.lookup(["w2@example.com"])["w2@example.com"].contact_id == "c-wesley"


# --- task shape ------------------------------------------------------------


def test_task_payload_is_keyed_on_the_message_and_carries_the_explanation():
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message()])
    contact = directory.lookup(["michelle@omnisure.com"])["michelle@omnisure.com"]
    payload = task_payload(_result(), contact=contact, company="OmniSure", matched_by="name", display_name="Michelle Earle")
    assert payload["id"] == task_id_for("m1") == "ccc-email-m1"
    assert payload["title"] == "Reply to Michelle Foster Earle: Re: independent verification"
    assert payload["source"] == "ccc_email"
    assert payload["source_ref"] == "m1"
    assert payload["priority"] == "high"
    assert payload["organization_name"] == "OmniSure"
    assert payload["context_snippet"] == "owed reply: known contact, thread tail, 7d"
    assert payload["raw_metadata"]["contact_matched_by"] == "name"
    assert payload["raw_metadata"]["mode"] == MODE_OWED_REPLY
    # RAV-1465: the description is a human paragraph, not the ranker's scores.
    assert payload["description"] == (
        'Michelle Foster Earle wrote on Sep 7 — "Re: independent verification". '
        "You have not replied in 7 days."
    )
    assert "Ranker:" not in payload["description"]
    assert payload["description_source"] == "ccc_email"


def test_task_payload_falls_back_to_display_name_then_address():
    p = task_payload(_result(), contact=None, company=None, matched_by=None, display_name="Michelle Earle")
    assert p["title"].startswith("Reply to Michelle Earle:")
    assert p["contact_id"] is None
    assert p["description"].startswith('Michelle Earle wrote on Sep 7')
    p = task_payload(_result(subject="  "), contact=None, company=None, matched_by=None, display_name=None)
    assert p["title"] == "Reply to michelle@omnisure.com: (no subject)"
    assert '"(no subject)"' in p["description"]


def test_description_names_the_thread_contact_when_reached_via_thread():
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message()])
    result = _result(from_addr="mark@omnisure.com")
    contact = directory.lookup(["michelle@omnisure.com"])["michelle@omnisure.com"]
    p = task_payload(result, contact=contact, company="OmniSure", matched_by="thread", display_name="Mark Batten")
    assert p["description"] == (
        'Mark Batten wrote on Sep 7 — "Re: independent verification". You have not replied in 7 days. '
        "The thread is with Michelle Foster Earle (OmniSure)."
    )


def test_description_names_the_thread_contact_without_a_company():
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message()])
    result = _result(from_addr="wesley@example.com")
    contact = directory.lookup(["michelle@omnisure.com"])["michelle@omnisure.com"]
    p = task_payload(result, contact=contact, company=None, matched_by="thread", display_name="Mark Batten")
    assert "The thread is with Michelle Foster Earle." in p["description"]
    assert "(" not in p["description"].split("The thread is with")[1]


def test_description_names_a_cold_open_when_the_explanation_says_so():
    p = task_payload(_result(explanation="cold open — you have never replied in thread t1; score = 60"),
                      contact=None, company=None, matched_by=None, display_name="Michelle Earle")
    assert p["description"].endswith("You have never replied in this thread.")


def test_description_names_an_earlier_reply_when_the_explanation_says_so():
    p = task_payload(_result(explanation="you have sent a message in thread t1 before; score = 60"),
                      contact=None, company=None, matched_by=None, display_name="Michelle Earle")
    assert p["description"].endswith("You last replied earlier in this thread.")


def test_description_for_several_unanswered_messages_names_the_count_and_debt_start():
    result = _result(unanswered_count=3, debt_since=NOW - timedelta(days=10), subject="Re: proposal")
    p = task_payload(result, contact=None, company=None, matched_by=None, display_name="Michelle Earle")
    assert p["description"] == (
        'Michelle Earle followed up on Sep 7 — "Re: proposal". '
        "3 messages have gone unanswered since Sep 4."
    )


# --- plan ------------------------------------------------------------------


def test_plan_posts_owed_replies_only_skips_existing_and_ignores_arrivals():
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message()])
    results = [  # one thread each: the ranker only ever owes one tail per thread
        _result(message_id="owed-new", thread_id="t-new"),
        _result(message_id="owed-old", thread_id="t-old"),
        _result(message_id="arrival", thread_id="t-arrival", mode=MODE_ARRIVAL, score=60),
        _result(message_id="gated", thread_id="t-gated", surfaced=False),
    ]
    plan = plan_sync(results, directory=directory, existing_task_ids={"ccc-email-owed-old"})
    assert [p["id"] for p in plan.create] == ["ccc-email-owed-new"]
    assert plan.skipped_existing == ("ccc-email-owed-old",)
    assert plan.ignored == ("arrival",)
    assert plan.create[0]["contact_id"] == "c-michelle"


def test_plan_can_include_arrivals_when_asked():
    directory = CccContactDirectory.from_rows(ROWS)
    results = [_result(message_id="arrival", mode=MODE_ARRIVAL, score=60)]
    plan = plan_sync(results, directory=directory, existing_task_ids=(), include_arrivals=True)
    assert [p["id"] for p in plan.create] == ["ccc-email-arrival"]
    assert plan.create[0]["priority"] == "low"


# --- bulk-sender and person gating -----------------------------------------


def test_bulk_senders_never_match_by_name_even_when_dex_imported_them_as_contacts():
    rows = ROWS + [ContactRow(id="c-dex", name="Dex"), ContactRow(id="c-nextdoor", name="Nextdoor Local News"),
                   ContactRow(id="c-strike", name="Strike Gently"), ContactRow(id="c-abel", name="Abel Moreno")]
    directory = CccContactDirectory.from_rows(rows)
    assert "dex" not in directory.by_name and "nextdoor local news" not in directory.by_name
    directory.observe([
        _message(message_id="a", from_addr="notify@updates.getdex.com", from_name="Dex"),
        _message(message_id="b", from_addr="reply@rs.email.nextdoor.com", from_name="Nextdoor Local News"),
        _message(message_id="c", from_addr="madeline@strikegently.co", from_name="Strike Gently"),
        _message(message_id="d", from_addr="jobs-noreply@linkedin.com", from_name="Michelle Earle"),
    ])
    found = directory.lookup(["notify@updates.getdex.com", "reply@rs.email.nextdoor.com", "madeline@strikegently.co", "jobs-noreply@linkedin.com"])
    assert found == {}  # none of those rows carry a company or title, so none is a person
    assert "jobs-noreply@linkedin.com" not in found  # person-shaped name on a bulk address is still bulk


def test_person_shaped_and_bulk_heuristics():
    assert person_shaped("Michelle Foster Earle") and person_shaped("Wesley Earle, AINS")
    assert not person_shaped("Dex") and not person_shaped("Nextdoor Local News") and not person_shaped("Tractor Supply Company")
    assert looks_like_bulk_sender("no-reply@substack.com") and looks_like_bulk_sender("hello@x.com")
    assert looks_like_bulk_sender("madeline@em.brand.com") and not looks_like_bulk_sender("michelle@omnisure.com")


# --- union corpus ------------------------------------------------------------


def test_union_corpus_merges_newest_first_and_unions_replied_threads():
    class C:
        def __init__(self, msgs, replied):
            self.msgs, self.replied = msgs, replied

        def recent_messages(self, **kw):
            return self.msgs

        def latest_messages_per_thread(self, **kw):
            return self.msgs

        def threads_with_message_from(self, thread_ids, addresses):
            return self.replied

    a = C([_message(message_id="old", ts=NOW - timedelta(days=3))], {"t-a"})
    b = C([_message(message_id="new", ts=NOW - timedelta(days=1))], {"t-b"})
    u = UnionCorpus([a, b])
    assert [m.message_id for m in u.recent_messages(since=NOW, until=NOW, limit=5)] == ["new", "old"]
    assert [m.message_id for m in u.latest_messages_per_thread(since=NOW, until=NOW, limit=1)] == ["new"]
    assert u.threads_with_message_from([], []) == {"t-a", "t-b"}


def test_a_person_shaped_dex_row_without_company_or_title_is_not_a_person():
    directory = CccContactDirectory.from_rows([ContactRow(id="x", name="Abel Moreno")])
    directory.observe([_message(from_addr="abel@events.example", from_name="Abel Moreno")])
    assert directory.lookup(["abel@events.example"]) == {}


# --- the thread's task follows the thread's tail (2026-09-15) ---------------


def test_plan_updates_the_threads_open_task_instead_of_raising_a_second_one():
    """Mark replied in Michelle's thread. One action item per owed thread: the
    existing open task is retitled to the new tail, not duplicated."""
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message(message_id="m-mark", from_addr="mark@omnisure.com", from_name="Mark Batten")])
    old = _result(message_id="m-michelle", thread_id="t1", surfaced=False, mode=MODE_ARRIVAL, score=5)
    new = _result(message_id="m-mark", thread_id="t1", from_addr="mark@omnisure.com", subject="Re: Consulting",
                  contact_id="c-michelle", contact_name="Michelle Foster Earle")

    plan = plan_sync([new, old], directory=directory, existing_task_ids={"ccc-email-m-michelle": "triage"})

    assert plan.create == ()
    assert plan.skipped_existing == ()
    assert [u["id"] for u in plan.update] == ["ccc-email-m-michelle"]
    assert plan.update[0]["title"] == "Reply to Mark Batten: Re: Consulting"
    assert "Mark Batten" in plan.update[0]["description"]
    assert plan.update[0]["raw_metadata"]["source_ref"] == "m-mark"


def test_plan_raises_a_fresh_task_when_the_threads_old_task_is_closed():
    directory = CccContactDirectory.from_rows(ROWS)
    old = _result(message_id="m-michelle", thread_id="t1", surfaced=False, mode=MODE_ARRIVAL, score=5)
    new = _result(message_id="m-mark", thread_id="t1", from_addr="mark@omnisure.com")
    for closed in ("completed", "rejected", "withdrawn"):
        plan = plan_sync([new, old], directory=directory, existing_task_ids={"ccc-email-m-michelle": closed})
        assert [p["id"] for p in plan.create] == ["ccc-email-m-mark"], closed
        assert plan.update == ()


def test_plan_still_accepts_a_bare_set_of_ids_and_treats_them_as_open():
    directory = CccContactDirectory.from_rows(ROWS)
    old = _result(message_id="m-michelle", thread_id="t1", surfaced=False, mode=MODE_ARRIVAL, score=5)
    new = _result(message_id="m-mark", thread_id="t1", from_addr="mark@omnisure.com")
    plan = plan_sync([new, old], directory=directory, existing_task_ids={"ccc-email-m-michelle"})
    assert plan.create == () and [u["id"] for u in plan.update] == ["ccc-email-m-michelle"]
    assert plan.update[0]["description_kept"] is False
    assert "description" in plan.update[0]


def test_plan_accepts_a_mapping_of_status_and_description_source_the_new_shape():
    """The hub-contract shape added in amp-live-aid: id -> {"status",
    "description_source"}. `_normalize_existing` must keep accepting the two
    older shapes too (bare iterable, id -> bare status string)."""
    directory = CccContactDirectory.from_rows(ROWS)
    old = _result(message_id="m-michelle", thread_id="t1", surfaced=False, mode=MODE_ARRIVAL, score=5)
    new = _result(message_id="m-mark", thread_id="t1", from_addr="mark@omnisure.com")
    plan = plan_sync(
        [new, old], directory=directory,
        existing_task_ids={"ccc-email-m-michelle": {"status": "triage", "description_source": "ccc_email"}},
    )
    assert plan.create == () and [u["id"] for u in plan.update] == ["ccc-email-m-michelle"]
    assert plan.update[0]["description_kept"] is False
    assert "description" in plan.update[0]


def test_plan_never_overwrites_a_description_nate_has_edited():
    """2026-09-15 ruling: Nate's edits win. The sync plan only rewrites a
    description it wrote and he has not touched — so an open task whose
    `description_source` is his own user id (anything but None/"ccc_email")
    gets its title updated but keeps its description."""
    directory = CccContactDirectory.from_rows(ROWS)
    old = _result(message_id="m-michelle", thread_id="t1", surfaced=False, mode=MODE_ARRIVAL, score=5)
    new = _result(message_id="m-mark", thread_id="t1", from_addr="mark@omnisure.com", subject="Re: Consulting")
    plan = plan_sync(
        [new, old], directory=directory,
        existing_task_ids={"ccc-email-m-michelle": {"status": "triage", "description_source": "user-nate"}},
    )
    assert plan.create == ()
    update = plan.update[0]
    assert update["id"] == "ccc-email-m-michelle"
    assert update["title"] == "Reply to mark@omnisure.com: Re: Consulting"  # title always updates
    assert "description" not in update
    assert update["description_kept"] is True


def test_task_payload_names_the_sender_and_links_the_known_contact_reached_via_the_thread():
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message(message_id="m-mark", from_addr="mark@omnisure.com", from_name="Mark Batten")])
    result = _result(message_id="m-mark", from_addr="mark@omnisure.com", subject="Re: Consulting",
                     contact_id="c-michelle", contact_name="Michelle Foster Earle")
    plan = plan_sync([result], directory=directory, existing_task_ids=())
    p = plan.create[0]
    assert p["title"] == "Reply to Mark Batten: Re: Consulting"
    assert p["contact_id"] == "c-michelle"
    assert p["contact_name"] == "Michelle Foster Earle"
    assert p["organization_name"] == "OmniSure"
    assert p["raw_metadata"]["contact_matched_by"] == "thread"


def test_task_payload_for_a_relayed_direct_message_says_where_to_reply():
    directory = CccContactDirectory.from_rows(ROWS)
    result = _result(message_id="m-dm", thread_id="t-dm", from_addr="no-reply@substack.com",
                     subject="💬 New message from Paul Gibbons", contact_id="relay:substack",
                     contact_name="Paul Gibbons", relay="substack")
    p = plan_sync([result], directory=directory, existing_task_ids=()).create[0]
    assert p["title"] == "Reply on Substack to Paul Gibbons: New message from Paul Gibbons"
    assert p["contact_id"] is None
    assert p["contact_name"] == "Paul Gibbons"
    assert "https://substack.com/inbox" in p["description"]
    assert p["raw_metadata"]["relay"] == "substack"
    # RAV-1465: no scores in the description, and no excerpt when the subject
    # carries nothing beyond Substack's own boilerplate.
    assert p["description"] == "Paul Gibbons sent you a direct message on Substack on Sep 7. Reply at https://substack.com/inbox."
    assert p["description_source"] == "ccc_email"


def test_task_payload_for_a_relayed_direct_message_carries_an_excerpt_when_the_subject_has_one():
    directory = CccContactDirectory.from_rows(ROWS)
    result = _result(message_id="m-dm", thread_id="t-dm", from_addr="no-reply@substack.com",
                     subject="💬 New message from Paul Gibbons: loved your last post",
                     contact_id="relay:substack", contact_name="Paul Gibbons", relay="substack")
    p = plan_sync([result], directory=directory, existing_task_ids=()).create[0]
    assert p["description"] == (
        'Paul Gibbons sent you a direct message on Substack on Sep 7: "loved your last post". '
        "Reply at https://substack.com/inbox."
    )


def test_observing_and_union_corpora_forward_thread_history_and_register_names():
    from core.mail_reads import InMemoryMailCorpus
    a = InMemoryMailCorpus(messages=[_message(message_id="m1", thread_id="t", from_addr="michelle@omnisure.com", from_name="Michelle Earle")])
    b = InMemoryMailCorpus(messages=[_message(message_id="m2", thread_id="t", from_addr="mark@omnisure.com", from_name="Mark Batten", ts=NOW + timedelta(hours=1))])
    directory = CccContactDirectory.from_rows(ROWS)
    corpus = ObservingCorpus(UnionCorpus([a, b]), directory)
    rows = corpus.thread_messages(["t"])
    assert [m.message_id for m in rows] == ["m1", "m2"]
    assert directory.display_names["michelle@omnisure.com"] == "Michelle Earle"
    assert directory.lookup(["michelle@omnisure.com"])["michelle@omnisure.com"].contact_id == "c-michelle"
