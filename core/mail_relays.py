"""Relays — platform notifications that carry a person's direct message.

Some conversations never touch the mailbox as mail. A Substack DM arrives only
as `no-reply@substack.com` "💬 New message from <Name>", the text in the
snippet, the reply button pointing back at the platform. Under the ranker's
rule that sender is unrepliable and the counterparty is not in contacts, so
the message is gated forever — which is how a "very, very important" one sat
unread (Nate, 2026-09-15).

A direct message is a person addressing the operator by construction. It is
not a blast, so it does not need the known-contact test that exists to keep
blasts out. This module *unwraps* the relay: it names the counterparty, the
channel, and where the reply happens. Nothing here decides relevance — the
ranker still applies grace, horizon, and thread-tail.

Follower, subscriber, digest, and comment notifications are **not** relays:
they are not addressed to the operator personally and stay in arrival mode.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .mail_reads import MailMessage, normalize_address

_INVISIBLE = re.compile(r"[͏​‌‍﻿­]+")


@dataclass(frozen=True)
class Relay:
    channel: str            # "substack"
    counterparty: str       # "Paul Gibbons"
    reply_url: str          # where the reply actually happens
    excerpt: str            # the message text as carried by the notification


def _clean(text: str) -> str:
    text = _INVISIBLE.sub("", text or "")
    text = text.replace("💬", "")
    return " ".join(text.split())


_SUBSTACK_DM_SUBJECT = re.compile(r"^\s*(?:💬\s*)?New message from (?P<name>.+?)\s*$")


def relay_for(message: MailMessage) -> Relay | None:
    """The relay this message carries, or `None` for ordinary mail."""
    sender = normalize_address(message.from_addr)
    if sender == "no-reply@substack.com":
        match = _SUBSTACK_DM_SUBJECT.match(_clean(message.subject))
        if match:
            return Relay(
                channel="substack",
                counterparty=match.group("name").strip(),
                reply_url="https://substack.com/inbox",
                excerpt=_clean(message.snippet)[:300],
            )
    return None
