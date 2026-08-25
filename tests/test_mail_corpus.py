"""Mail corpus chunker — the chunker is the product, so it is the test surface."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.mail_corpus import (
    DEFAULT_MAX_BODY_CHARS,
    EMBEDDABLE_PARTS,
    PARTS,
    MailMessage,
    embeddable_exemplars,
    normalize_for_template,
    part_histogram,
    segment_message,
    segment_text,
    template_id,
)

TS = datetime(2026, 8, 24, 14, 30, 0, tzinfo=timezone.utc)


def _parts(pairs):
    return [part for part, _text in pairs]


def _text_for(pairs, part):
    return "\n".join(text for label, text in pairs if label == part)


class TestTaxonomy:
    def test_nine_parts_exactly(self):
        assert len(PARTS) == 9
        assert set(PARTS) == {
            "subject", "body", "quoted", "signature", "greeting",
            "disclaimer", "boilerplate", "forward_header", "autoreply",
        }

    def test_only_subject_and_body_are_embedded(self):
        assert EMBEDDABLE_PARTS == {"subject", "body"}


class TestSegmentation:
    def test_subject_is_its_own_chunk_first(self):
        pairs = segment_text("Technical screen", "Sounds good, see you then.")
        assert pairs[0] == ("subject", "Technical screen")

    def test_empty_subject_is_not_emitted(self):
        pairs = segment_text("   ", "Just the body.")
        assert _parts(pairs) == ["body"]

    def test_empty_body_yields_subject_only(self):
        assert segment_text("Ping", "") == [("subject", "Ping")]

    def test_greeting_signoff_signature_quoted_disclaimer(self):
        body = (
            "Hi Nate,\n"
            "\n"
            "The team reviewed the doc and would like a technical screen.\n"
            "\n"
            "Best regards,\n"
            "Dana\n"
            "\n"
            "--\n"
            "Dana Whitfield\n"
            "Senior Technical Recruiter, Acme Corp\n"
            "dana@acme.example | +1 512-555-0134\n"
            "\n"
            "On Mon, Aug 24, 2026 at 9:12 AM Nate <nate@example.com> wrote:\n"
            "> Attached is the doc.\n"
            "\n"
            "This email and any attachments are confidential and intended solely\n"
            "for the addressee. If you are not the intended recipient, delete it.\n"
        )
        pairs = segment_text("Re: Technical screen", body)
        assert _parts(pairs) == [
            "subject", "greeting", "body", "greeting",
            "signature", "quoted", "disclaimer",
        ]

    def test_quoted_trail_is_not_body(self):
        pairs = segment_text("Re: doc", "Sure.\n\n> the original text\n> more original\n")
        assert "the original text" not in _text_for(pairs, "body")
        assert "the original text" in _text_for(pairs, "quoted")

    def test_forward_header_block_is_labelled(self):
        body = (
            "FYI.\n"
            "\n"
            "---------- Forwarded message ---------\n"
            "From: Someone <someone@example.com>\n"
            "Date: Mon, Aug 24, 2026 at 9:12 AM\n"
            "Subject: The original\n"
            "To: Nate <nate@example.com>\n"
            "\n"
            "Original body text here.\n"
        )
        pairs = segment_text("Fwd: The original", body)
        assert _parts(pairs) == ["subject", "body", "forward_header", "quoted"]
        assert "From: Someone" in _text_for(pairs, "forward_header")
        assert "Original body text here." in _text_for(pairs, "quoted")

    def test_outlook_original_message_marker(self):
        body = "Answering below.\n\n-----Original Message-----\nFrom: X\nOld text.\n"
        pairs = segment_text("Re: x", body)
        assert "Old text." in _text_for(pairs, "quoted")

    def test_outlook_bare_header_block_starts_the_trail(self):
        body = (
            "Quick answer.\n"
            "\n"
            "From: Someone <someone@example.com>\n"
            "Sent: Monday, August 24, 2026 9:12 AM\n"
            "To: Nate Walker\n"
            "Subject: The original\n"
            "\n"
            "Original body.\n"
        )
        pairs = segment_text("Re: The original", body)
        assert "Original body." in _text_for(pairs, "quoted")
        assert "Original body." not in _text_for(pairs, "body")

    def test_multiline_attribution_is_quoted(self):
        body = (
            "Thanks.\n"
            "\n"
            "On Mon, Aug 24, 2026 at 9:12 AM Dana Whitfield\n"
            "<dana@acme.example> wrote:\n"
            "Old content.\n"
        )
        pairs = segment_text("Re: x", body)
        assert "On Mon, Aug 24" in _text_for(pairs, "quoted")
        assert "Old content." in _text_for(pairs, "quoted")

    def test_boilerplate_lines(self):
        body = "See attached.\n\nSent from my iPhone\n"
        pairs = segment_text("doc", body)
        assert _text_for(pairs, "boilerplate") == "Sent from my iPhone"

    def test_unsubscribe_footer_is_boilerplate(self):
        body = "New jobs for you.\n\nUnsubscribe from these alerts\n"
        pairs = segment_text("Job alert", body)
        assert "Unsubscribe" in _text_for(pairs, "boilerplate")

    def test_autoreply_body_is_relabelled(self):
        body = "Hi,\n\nI am currently out of the office until September 2 with limited email access.\n"
        pairs = segment_text("Automatic reply: Technical screen", body)
        assert "autoreply" in _parts(pairs)
        assert "body" not in _parts(pairs)

    def test_auto_submitted_header_forces_autoreply(self):
        pairs = segment_text("Ticket 123", "Your request was received.", auto_submitted="auto-replied")
        assert "autoreply" in _parts(pairs)

    def test_trailing_contact_block_without_delimiter_is_signature(self):
        body = (
            "Happy to chat next week about the role.\n"
            "\n"
            "Dana Whitfield\n"
            "Senior Recruiter\n"
            "dana@acme.example\n"
        )
        pairs = segment_text("Role", body)
        assert "Dana Whitfield" in _text_for(pairs, "signature")
        assert "Happy to chat" in _text_for(pairs, "body")

    def test_short_message_is_not_swallowed_by_the_signature_heuristic(self):
        pairs = segment_text("q", "call me at 512-555-0134")
        assert _parts(pairs) == ["subject", "body"]

    def test_nothing_is_discarded(self):
        body = (
            "Hi Nate,\n\nHere is the update.\n\n--\nDana\ndana@acme.example\n\n"
            "> quoted bit\n"
        )
        pairs = segment_text("Update", body)
        rejoined = "\n".join(text for part, text in pairs if part != "subject")
        for fragment in ("Hi Nate,", "Here is the update.", "Dana", "> quoted bit"):
            assert fragment in rejoined

    def test_long_body_splits_on_paragraph_boundaries(self):
        paragraph = "word " * 120  # ~600 chars
        body = "\n\n".join(paragraph.strip() for _ in range(8))
        pairs = segment_text("Long", body, max_body_chars=1000)
        body_chunks = [text for part, text in pairs if part == "body"]
        assert len(body_chunks) > 1
        assert all(len(chunk) <= 1000 for chunk in body_chunks)

    def test_oversized_single_paragraph_is_hard_split(self):
        pairs = segment_text("", "x" * 5000, max_body_chars=1000)
        assert all(len(text) <= 1000 for _part, text in pairs)

    def test_default_body_budget_is_applied(self):
        pairs = segment_text("", "y" * (DEFAULT_MAX_BODY_CHARS * 2))
        assert len([p for p, _ in pairs if p == "body"]) == 2


class TestTemplateCollapse:
    def test_names_collapse(self):
        a = normalize_for_template("Alice Smith viewed your profile")
        b = normalize_for_template("Bob Jones viewed your profile")
        assert a == b

    def test_greeting_first_name_collapses(self):
        assert normalize_for_template("Hi Nate,") == normalize_for_template("Hi Dana,")

    def test_counts_dates_urls_and_emails_collapse(self):
        a = normalize_for_template(
            "You have 14 new jobs as of 2026-08-24. See https://x.example/a?b=1 or mail a@b.example"
        )
        b = normalize_for_template(
            "You have 3 new jobs as of 2026-01-02. See https://x.example/zzz or mail c@d.example"
        )
        assert a == b

    def test_different_templates_do_not_collide(self):
        assert template_id("body", "You have 14 new jobs") != template_id(
            "body", "Your invoice is ready"
        )

    def test_same_template_same_id(self):
        assert template_id("body", "Alice Smith viewed your profile") == template_id(
            "body", "Bob Jones viewed your profile"
        )

    def test_part_is_part_of_the_key(self):
        assert template_id("subject", "Weekly digest") != template_id("body", "Weekly digest")

    def test_content_free_chunk_has_empty_template_id(self):
        assert template_id("body", "   \n  ") == ""

    def test_template_id_is_stable_hex(self):
        value = template_id("body", "hello world")
        assert len(value) == 32
        assert value == template_id("body", "hello world")


class TestSegmentMessage:
    def _message(self, **overrides) -> MailMessage:
        base = dict(
            message_id="msg-1",
            thread_id="thr-1",
            ts=TS,
            subject="Technical screen",
            body_text="Hi Nate,\n\nAre you free Tuesday?\n\nBest,\nDana\n",
        )
        base.update(overrides)
        return MailMessage(**base)

    def test_chunks_carry_message_identity_and_sequence(self):
        chunks = segment_message(self._message())
        assert [chunk.seq for chunk in chunks] == list(range(len(chunks)))
        assert {chunk.message_id for chunk in chunks} == {"msg-1"}
        assert {chunk.thread_id for chunk in chunks} == {"thr-1"}
        assert {chunk.ts for chunk in chunks} == {TS}

    def test_char_len_matches_text(self):
        for chunk in segment_message(self._message()):
            assert chunk.char_len == len(chunk.text)

    def test_embeddable_flag_follows_the_taxonomy(self):
        chunks = segment_message(self._message())
        for chunk in chunks:
            assert chunk.embeddable == (chunk.part in EMBEDDABLE_PARTS)

    def test_segmentation_is_deterministic(self):
        first = segment_message(self._message())
        second = segment_message(self._message())
        assert first == second

    def test_histogram_counts_every_part_key(self):
        histogram = part_histogram(segment_message(self._message()))
        assert set(histogram) >= set(PARTS)
        assert histogram["subject"] == 1

    def test_exemplars_collapse_repeated_machine_mail(self):
        messages = [
            self._message(
                message_id=f"msg-{index}",
                subject="LinkedIn digest",
                body_text=f"{name} viewed your profile\n",
            )
            for index, name in enumerate(["Alice Smith", "Bob Jones", "Cara Diaz"])
        ]
        chunks = [chunk for message in messages for chunk in segment_message(message)]
        exemplars = embeddable_exemplars(chunks)
        assert len(chunks) == 6  # 3 subjects + 3 bodies
        assert len(exemplars) == 2  # one subject exemplar, one body exemplar

    def test_exemplars_keep_distinct_human_mail(self):
        messages = [
            self._message(message_id="a", body_text="Can we move the screen to Thursday?"),
            self._message(message_id="b", body_text="The architecture doc is attached for review."),
        ]
        chunks = [chunk for message in messages for chunk in segment_message(message)]
        bodies = [c for c in embeddable_exemplars(chunks) if c.part == "body"]
        assert len(bodies) == 2


@pytest.mark.parametrize(
    "body",
    ["", "   ", "\n\n\n"],
)
def test_blank_bodies_are_safe(body):
    assert segment_text("subject only", body) == [("subject", "subject only")]
