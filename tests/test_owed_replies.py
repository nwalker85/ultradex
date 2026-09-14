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


def test_task_payload_falls_back_to_display_name_then_address():
    p = task_payload(_result(), contact=None, company=None, matched_by=None, display_name="Michelle Earle")
    assert p["title"].startswith("Reply to Michelle Earle:")
    assert p["contact_id"] is None
    p = task_payload(_result(subject="  "), contact=None, company=None, matched_by=None, display_name=None)
    assert p["title"] == "Reply to michelle@omnisure.com: (no subject)"


# --- plan ------------------------------------------------------------------


def test_plan_posts_owed_replies_only_skips_existing_and_ignores_arrivals():
    directory = CccContactDirectory.from_rows(ROWS)
    directory.observe([_message()])
    results = [
        _result(message_id="owed-new"),
        _result(message_id="owed-old"),
        _result(message_id="arrival", mode=MODE_ARRIVAL, score=60),
        _result(message_id="gated", surfaced=False),
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
