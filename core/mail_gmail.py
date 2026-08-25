"""Gmail full-message fetch for the private mail corpus.

The governed sweep in :mod:`core.jobsearch_gmail` deliberately stores only
thread IDs, a commitment and counts — that plane does not change. This module
is the *other* thing: the private Stage pull that needs headers and plaintext
bodies so the corpus can be chunked and embedded.

Auth is **reused**, not reimplemented: :func:`core.jobsearch_gmail.resolve_access_token`
and its refresh path are the single credential road (1Password
``op://ravenmask/Gmail OAuth - CCC Sense``).
"""
from __future__ import annotations

import base64
import binascii
import html as html_module
import re
import time
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import getaddresses
from typing import Any, Callable, Iterator, Mapping, Sequence

from .mail_corpus import MailMessage

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

#: The whole mailbox for the decided window. Relevance is computed downstream,
#: never declared here — a hand-authored query is a relevance model frozen at
#: authoring time.
DEFAULT_CORPUS_WINDOW_YEARS = 3
DEFAULT_MAIL_CORPUS_QUERY = f"newer_than:{DEFAULT_CORPUS_WINDOW_YEARS}y"

DEFAULT_PAGE_SIZE = 100
_MAX_ATTEMPTS = 5
_BACKOFF_BASE_SECONDS = 1.0

_TAG_RE = re.compile(r"<[^>]+>")
_BREAK_RE = re.compile(r"(?i)<\s*br\s*/?\s*>")
_BLOCK_END_RE = re.compile(r"(?i)</\s*(p|div|tr|li|h[1-6]|table|blockquote)\s*>")
_SCRIPT_STYLE_RE = re.compile(
    r"(?is)<\s*(script|style|head)\b.*?<\s*/\s*\1\s*>"
)
_BLANK_RUN_RE = re.compile(r"\n{3,}")


class GmailFetchError(RuntimeError):
    """Gmail refused or failed a request after retries."""


def corpus_query(
    *,
    years: int = DEFAULT_CORPUS_WINDOW_YEARS,
    before: datetime | None = None,
    extra: str = "",
) -> str:
    """Build the corpus query. ``before`` drives newest-first resumption."""
    parts = [f"newer_than:{int(years)}y"]
    if before is not None:
        parts.append(f"before:{before.astimezone(timezone.utc).strftime('%Y/%m/%d')}")
    if extra.strip():
        parts.append(extra.strip())
    return " ".join(parts)


def _request(
    client,
    url: str,
    *,
    access_token: str,
    params: Mapping[str, Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_attempts: int = _MAX_ATTEMPTS,
) -> dict:
    last_status = None
    for attempt in range(max_attempts):
        response = client.get(
            url,
            params=dict(params or {}),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        status = response.status_code
        if status < 400:
            try:
                return response.json()
            except ValueError as exc:
                raise GmailFetchError("gmail_malformed_response") from exc
        last_status = status
        if status in (429, 500, 502, 503, 504):
            retry_after = 0.0
            header = (response.headers or {}).get("Retry-After")
            if header:
                try:
                    retry_after = float(header)
                except (TypeError, ValueError):
                    retry_after = 0.0
            sleep(retry_after or _BACKOFF_BASE_SECONDS * (2**attempt))
            continue
        raise GmailFetchError(f"gmail_http_{status}")
    raise GmailFetchError(f"gmail_retries_exhausted_{last_status}")


def list_message_ids(
    *,
    access_token: str,
    query: str,
    client,
    page_token: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    include_spam_trash: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[str], str | None]:
    """One page of message IDs. Gmail returns them newest-first."""
    params: dict[str, Any] = {"q": query, "maxResults": int(page_size)}
    if include_spam_trash:
        params["includeSpamTrash"] = "true"
    if page_token:
        params["pageToken"] = page_token
    payload = _request(
        client, f"{GMAIL_API_BASE}/messages",
        access_token=access_token, params=params, sleep=sleep,
    )
    ids = [
        str(item["id"])
        for item in (payload.get("messages") or [])
        if item.get("id")
    ]
    return ids, payload.get("nextPageToken")


def iter_message_id_pages(
    *,
    access_token: str,
    query: str,
    client,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int | None = None,
    include_spam_trash: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[list[str]]:
    """Yield pages of IDs newest-first, so the corpus is useful before the
    full three-year pull completes."""
    page_token: str | None = None
    pages = 0
    while max_pages is None or pages < max_pages:
        ids, page_token = list_message_ids(
            access_token=access_token,
            query=query,
            client=client,
            page_token=page_token,
            page_size=page_size,
            include_spam_trash=include_spam_trash,
            sleep=sleep,
        )
        pages += 1
        if ids:
            yield ids
        if not page_token:
            return


def fetch_message(
    *,
    access_token: str,
    message_id: str,
    client,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """One full message: headers, MIME parts, labels, internalDate."""
    return _request(
        client,
        f"{GMAIL_API_BASE}/messages/{message_id}",
        access_token=access_token,
        params={"format": "full"},
        sleep=sleep,
    )


# --- MIME → plaintext -------------------------------------------------------
def decode_part_data(data: str | None) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError):
        return ""
    return raw.decode("utf-8", errors="replace")


def html_to_text(html: str) -> str:
    """Good-enough HTML flattening. No new dependency for a fallback path."""
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _BREAK_RE.sub("\n", text)
    text = _BLOCK_END_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html_module.unescape(text)
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n")]
    return _BLANK_RUN_RE.sub("\n\n", "\n".join(lines)).strip()


def _walk_parts(part: Mapping[str, Any] | None) -> Iterator[Mapping[str, Any]]:
    if not part:
        return
    yield part
    for child in part.get("parts") or []:
        yield from _walk_parts(child)


def extract_body_text(payload: Mapping[str, Any] | None) -> str:
    """Prefer ``text/plain``; fall back to flattened ``text/html``."""
    plain: list[str] = []
    html_parts: list[str] = []
    for part in _walk_parts(payload):
        mime = (part.get("mimeType") or "").lower()
        if part.get("filename"):
            continue
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        if mime == "text/plain":
            plain.append(decode_part_data(data))
        elif mime == "text/html":
            html_parts.append(decode_part_data(data))
    if plain:
        return _BLANK_RUN_RE.sub("\n\n", "\n".join(plain).replace("\r\n", "\n")).strip()
    if html_parts:
        return html_to_text("\n".join(html_parts))
    return ""


def extract_attachment_names(payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    names = [
        str(part["filename"])
        for part in _walk_parts(payload)
        if part.get("filename")
    ]
    seen: list[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return value


def _headers_map(payload: Mapping[str, Any] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header in (payload or {}).get("headers") or []:
        name = str(header.get("name") or "").lower()
        if name and name not in headers:
            headers[name] = str(header.get("value") or "")
    return headers


def _addresses(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    found: list[str] = []
    for _name, address in getaddresses([_decode_header_value(value)]):
        cleaned = address.strip().lower()
        if cleaned and cleaned not in found:
            found.append(cleaned)
    return tuple(found)


def _from_parts(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    pairs = getaddresses([_decode_header_value(value)])
    if not pairs:
        return "", ""
    name, address = pairs[0]
    return address.strip().lower(), name.strip()


def parse_message(raw: Mapping[str, Any], *, source_ref: str = "") -> MailMessage:
    """Flatten one Gmail ``format=full`` message into a :class:`MailMessage`."""
    message_id = str(raw.get("id") or "")
    if not message_id:
        raise GmailFetchError("gmail_message_missing_id")
    payload = raw.get("payload") or {}
    headers = _headers_map(payload)

    internal = raw.get("internalDate")
    try:
        ts = datetime.fromtimestamp(int(internal) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        ts = datetime.fromtimestamp(0, tz=timezone.utc)

    from_addr, from_name = _from_parts(headers.get("from", ""))
    attachments = extract_attachment_names(payload)
    history_id = str(raw.get("historyId") or "")
    ref = source_ref or (f"gmail:{history_id}" if history_id else "gmail:full")

    return MailMessage(
        message_id=message_id,
        thread_id=str(raw.get("threadId") or ""),
        ts=ts,
        from_addr=from_addr,
        from_name=from_name,
        to_addrs=_addresses(headers.get("to", "")),
        cc_addrs=_addresses(headers.get("cc", "")),
        subject=_decode_header_value(headers.get("subject", "")),
        labels=tuple(str(label) for label in (raw.get("labelIds") or [])),
        snippet=html_module.unescape(str(raw.get("snippet") or "")),
        body_text=extract_body_text(payload),
        has_attachments=bool(attachments),
        attachment_names=attachments,
        size_estimate=int(raw.get("sizeEstimate") or 0),
        source_ref=ref,
        auto_submitted=headers.get("auto-submitted", ""),
    )


def fetch_messages(
    message_ids: Sequence[str],
    *,
    access_token: str,
    client,
    sleep: Callable[[float], None] = time.sleep,
    on_error: Callable[[str, Exception], None] | None = None,
) -> list[MailMessage]:
    """Fetch and parse a batch. A single bad message never kills a backfill."""
    messages: list[MailMessage] = []
    for message_id in message_ids:
        try:
            raw = fetch_message(
                access_token=access_token,
                message_id=message_id,
                client=client,
                sleep=sleep,
            )
            messages.append(parse_message(raw))
        except (GmailFetchError, KeyError, ValueError) as exc:
            if on_error is None:
                raise
            on_error(message_id, exc)
    return messages
