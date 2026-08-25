"""Tests for Omnichannel In-App Messaging & Dispatch Engine (Milestone M3, Feature F7)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.models import Base, ContactDB
from core.jobsearch_messaging import (
    ComposeMessageRequest,
    GmailMessagingClient,
    LinkedInMessagingAdapter,
    MessageChannel,
    MessageStatus,
    OmnichannelDispatcher,
    OmnichannelOutreachSender,
    OutboxMessage,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_gmail_client_builds_valid_mime_headers() -> None:
    client = GmailMessagingClient(sender_email="nate@theviking.ai", sender_name="Nate Walker")
    msg = client.build_mime_message(
        to_address="recruiter@anthropic.com",
        subject="Follow-up on VP of Engineering",
        body_text="Hi Alex, thanks for connecting.",
    )

    assert "Nate Walker <nate@theviking.ai>" in msg["From"]
    assert msg["To"] == "recruiter@anthropic.com"
    assert msg["Subject"] == "Follow-up on VP of Engineering"
    assert msg["Message-ID"].startswith("<") and msg["Message-ID"].endswith(">")
    assert "theviking.ai" in msg["Message-ID"]
    assert msg.get_content().strip() == "Hi Alex, thanks for connecting."


def test_gmail_client_builds_threading_headers_when_in_reply_to_present() -> None:
    client = GmailMessagingClient()
    in_reply_to_id = "<CAL-12345@mail.gmail.com>"
    references_id = "<ROOT-001@mail.gmail.com> <CAL-12345@mail.gmail.com>"

    msg = client.build_mime_message(
        to_address="sarah@deepgram.com",
        subject="Re: Senior Director Role",
        body_text="Looking forward to chatting tomorrow.",
        in_reply_to=in_reply_to_id,
        references=references_id,
    )

    assert msg["In-Reply-To"] == in_reply_to_id
    assert msg["References"] == references_id


def test_gmail_client_encodes_urlsafe_base64_correctly() -> None:
    client = GmailMessagingClient()
    msg = client.build_mime_message(
        to_address="test@example.com",
        subject="Test MIME",
        body_text="Hello world!",
    )
    raw = client.encode_raw_message(msg)

    # Validate that raw decodes properly
    decoded_bytes = base64.urlsafe_b64decode(raw)
    decoded_str = decoded_bytes.decode("utf-8", errors="replace")
    assert "Subject: Test MIME" in decoded_str
    assert "Hello world!" in decoded_str


@pytest.mark.asyncio
async def test_gmail_client_send_message_dispatches_to_google_sent() -> None:
    client = GmailMessagingClient()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        assert request.headers["Authorization"] == "Bearer mock-access-token"
        body = json.loads(request.content.decode())
        assert "raw" in body
        assert body.get("threadId") == "thread-99"
        return httpx.Response(200, json={"id": "gmail-sent-001", "threadId": "thread-99"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_http_client:
        res = await client.send_message(
            access_token="mock-access-token",
            to_address="recruiter@openai.com",
            subject="Re: Principal AI Architect",
            body_text="Here is my availability...",
            thread_id="thread-99",
            client=mock_http_client,
        )

    assert res["id"] == "gmail-sent-001"
    assert res["threadId"] == "thread-99"


@pytest.mark.asyncio
async def test_gmail_client_create_draft_posts_to_drafts_endpoint() -> None:
    client = GmailMessagingClient()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
        body = json.loads(request.content.decode())
        assert "message" in body
        assert "raw" in body["message"]
        return httpx.Response(200, json={"id": "draft-001", "message": {"id": "msg-draft-1"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_http_client:
        res = await client.create_draft(
            access_token="mock-access-token",
            to_address="recruiter@scale.com",
            subject="Draft reply",
            body_text="Draft content here.",
            client=mock_http_client,
        )

    assert res["id"] == "draft-001"


@pytest.mark.asyncio
async def test_gmail_client_handles_http_errors_fail_closed() -> None:
    client = GmailMessagingClient()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid Credentials", "code": 401}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_http_client:
        with pytest.raises(RuntimeError) as exc_info:
            await client.send_message(
                access_token="invalid-token",
                to_address="bad@example.com",
                subject="Fail test",
                body_text="Body",
                client=mock_http_client,
            )
        assert "Gmail send failed with HTTP 401" in str(exc_info.value)


def test_linkedin_adapter_validates_character_limits() -> None:
    adapter = LinkedInMessagingAdapter()

    # Valid short message
    adapter.validate_message("Hello on LinkedIn", is_inmail=False)
    adapter.validate_message("Hello on InMail", is_inmail=True)

    # InMail limit: 1,900 chars
    long_inmail = "x" * 1901
    with pytest.raises(ValueError) as exc:
        adapter.validate_message(long_inmail, is_inmail=True)
    assert "exceeds maximum allowed (1900 chars)" in str(exc.value)

    # DM limit: 8,000 chars
    long_dm = "y" * 8001
    with pytest.raises(ValueError) as exc:
        adapter.validate_message(long_dm, is_inmail=False)
    assert "exceeds maximum allowed (8000 chars)" in str(exc.value)


def test_linkedin_adapter_generates_thread_and_profile_urls() -> None:
    adapter = LinkedInMessagingAdapter()
    assert adapter.generate_direct_link("satyanadella") == "https://www.linkedin.com/in/satyanadella/"
    assert adapter.generate_direct_link("https://www.linkedin.com/in/nate-walker/") == "https://www.linkedin.com/in/nate-walker/"
    assert adapter.generate_thread_link("2-MzEyNDU=") == "https://www.linkedin.com/messaging/thread/2-MzEyNDU=/"


@pytest.mark.asyncio
async def test_linkedin_adapter_stages_message() -> None:
    adapter = LinkedInMessagingAdapter()
    staged = await adapter.stage_message(
        recipient_handle="sam-altman",
        subject="AI Infrastructure Alignment",
        body_text="Great chatting at the summit.",
        thread_id="thread-li-44",
    )

    assert staged["platform"] == "linkedin"
    assert staged["recipient"] == "sam-altman"
    assert staged["action_url"] == "https://www.linkedin.com/messaging/thread/thread-li-44/"
    assert "staged_at" in staged


def test_dispatcher_prepares_message_with_sha256_commitment(db_session: Session) -> None:
    dispatcher = OmnichannelDispatcher(db=db_session)
    req = ComposeMessageRequest(
        recipient_address="recruiter@anthropic.com",
        subject="CTO Scope Conversation",
        body_text="Looking forward to speaking about the platform vision.",
        channel=MessageChannel.GMAIL,
        recipient_name="Sarah",
    )

    outbox = dispatcher.prepare_message(req)
    assert outbox.status == MessageStatus.PENDING_APPROVAL
    assert outbox.message_commitment.startswith("sha256:")
    assert len(outbox.message_commitment) == 71  # "sha256:" + 64 hex chars


@pytest.mark.asyncio
async def test_dispatcher_dispatch_appends_to_contact_communication_history(db_session: Session) -> None:
    contact = ContactDB(
        id="contact-dex-77",
        name="Dario Amodei",
        email="dario@anthropic.com",
        company="Anthropic",
        job_title="CEO",
        advocacy_score=95.0,
        communication_history=[],
        last_contacted=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(contact)
    db_session.commit()

    dispatcher = OmnichannelDispatcher(db=db_session)
    outbox = OutboxMessage(
        id="msg-dispatch-01",
        channel=MessageChannel.GMAIL,
        recipient_address="dario@anthropic.com",
        recipient_id="contact-dex-77",
        subject="Scaling Agent Architectures",
        body_text="Hi Dario, following up on our discussion regarding sovereign AI systems.",
        thread_id="th-dario-1",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "gmail-dario-sent", "threadId": "th-dario-1"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        res = await dispatcher.dispatch_outbox_message(
            message=outbox,
            access_token="mock-token-xyz",
            client=mock_client,
        )

    assert res.success is True
    assert res.external_id == "gmail-dario-sent"
    assert outbox.status == MessageStatus.SENT

    # Verify ContactDB ledger updated
    updated_contact = db_session.get(ContactDB, "contact-dex-77")
    assert updated_contact is not None
    assert len(updated_contact.communication_history) == 1
    hist_entry = updated_contact.communication_history[0]
    assert hist_entry["channel"] == "gmail"
    assert hist_entry["direction"] == "outbound"
    assert hist_entry["subject"] == "Scaling Agent Architectures"
    assert hist_entry["evidence_ref"].startswith("evidence-gmail-")
    assert hist_entry["thread_id"] == "th-dario-1"
    assert updated_contact.last_contacted is not None


@pytest.mark.asyncio
async def test_outreach_sender_protocol_compliance() -> None:
    sender = OmnichannelOutreachSender()

    evidence_gmail = await sender.send(
        outreach_id="outreach-101",
        channel="gmail",
        message_commitment="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        idempotency_key="idem-key-1",
    )
    assert evidence_gmail.startswith("evidence-gmail-")

    evidence_li = await sender.send(
        outreach_id="outreach-102",
        channel="linkedin",
        message_commitment="sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        idempotency_key="idem-key-2",
    )
    assert evidence_li.startswith("evidence-linkedin-")

    with pytest.raises(ValueError) as exc:
        await sender.send(
            outreach_id="outreach-103",
            channel="unsupported_carrier",
            message_commitment="sha256:123",
            idempotency_key="idem-3",
        )
    assert "Unsupported outreach delivery channel" in str(exc.value)
