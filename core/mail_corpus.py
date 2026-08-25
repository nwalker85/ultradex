"""Mail corpus domain — segmentation and template collapse.

The private **Stage** layer under AAL Sense. Pure functions only: no Gmail, no
ClickHouse, no clock. Everything here is deterministic so the chunker can be
tested, argued with, and retrained against Consent's own labels.

Authority: ``~/docs/30-projects/career-command-center/DESIGN-mail-corpus-clickhouse.md``.

Boundary note: this module handles **plaintext bodies**. It lives below the
governed plane — the governed ``jobsearch_evidence_refs`` still carries only a
commitment plus a 240-char redacted summary, and nothing here writes there.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence

# --- the nine-part taxonomy -------------------------------------------------
# Every part is STORED. Only `subject` and `body` are marked for embedding;
# the rest are kept because they are evidence of what was actually sent.
PART_SUBJECT = "subject"
PART_BODY = "body"
PART_QUOTED = "quoted"
PART_SIGNATURE = "signature"
PART_GREETING = "greeting"
PART_DISCLAIMER = "disclaimer"
PART_BOILERPLATE = "boilerplate"
PART_FORWARD_HEADER = "forward_header"
PART_AUTOREPLY = "autoreply"

PARTS: tuple[str, ...] = (
    PART_SUBJECT,
    PART_BODY,
    PART_QUOTED,
    PART_SIGNATURE,
    PART_GREETING,
    PART_DISCLAIMER,
    PART_BOILERPLATE,
    PART_FORWARD_HEADER,
    PART_AUTOREPLY,
)

EMBEDDABLE_PARTS: frozenset[str] = frozenset({PART_SUBJECT, PART_BODY})

#: Body spans longer than this are split on paragraph boundaries. A chunk is an
#: embedding unit; a 40 KB newsletter body is not one.
#:
#: Sized to the *embedder's* window, not to taste: the deployed nomic-embed-text
#: on odin llama-swap caps each request at a fixed token batch (observed 512),
#: and ~1400 chars is ~370 tokens with headroom for token-dense prose. See
#: ``core.mail_embed.DEFAULT_MAX_WINDOW_CHARS``, which audio-app arrived at the
#: hard way. Oversized chunks still embed — the embedder splits and mean-pools
#: rather than failing — but a pooled vector is a blurrier vector, so the
#: chunker should hand it units that already fit.
DEFAULT_MAX_BODY_CHARS = 1400

# --- boundary heuristics ----------------------------------------------------
_QUOTE_CHAR_RE = re.compile(r"^\s*>")
_ORIGINAL_MESSAGE_RE = re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.I)
_FORWARD_MARKER_RE = re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}\s*$", re.I)
_BEGIN_FORWARD_RE = re.compile(r"^\s*Begin forwarded message:\s*$", re.I)
_HEADER_LINE_RE = re.compile(
    r"^\s*(From|To|Cc|Bcc|Sent|Date|Subject|Reply-To)\s*:\s", re.I
)
_FROM_HEADER_RE = re.compile(r"^\s*From\s*:\s", re.I)
_SIG_DELIM_RE = re.compile(r"^--\s*$")
_ON_PREFIX_RE = re.compile(r"^\s*On\b")
_WROTE_SUFFIX_RE = re.compile(r"\bwrote:\s*$", re.I)

_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|hiya|dear|good (morning|afternoon|evening)|greetings)\b"
    r"[^.!?]{0,40}[,:;!]?\s*$",
    re.I,
)
_SIGNOFF_RE = re.compile(
    r"^\s*(thanks so much|thanks again|many thanks|thanks|thank you|"
    r"best regards|kind regards|warm regards|best wishes|best|regards|"
    r"cheers|sincerely|yours truly|yours sincerely|all the best|talk soon|"
    r"looking forward to hearing from you|appreciate it|much appreciated)"
    r"[,.!]?\s*$",
    re.I,
)
_NAME_LINE_RE = re.compile(r"^\s*[A-Z][\w'.-]*(\s+[A-Z][\w'.-]*){0,3}[,.]?\s*$")

_DISCLAIMER_RE = re.compile(
    r"(this (e-?mail|message|communication|transmission)"
    r"( and any (attachments?|files?|documents?))?\s*"
    r"(is|are|may be|contains?)\s*(strictly\s*)?(confidential|privileged|intended)"
    r"|confidentiality (notice|statement)"
    r"|if you (are|were) not the intended recipient"
    r"|the information (contained )?in this (e-?mail|message|transmission)"
    r"|privileged and confidential"
    r"|any unauthoriz?sed (review|use|disclosure|dissemination))",
    re.I,
)

_BOILERPLATE_RE = re.compile(
    r"^\s*("
    r"sent from my [\w\s]+"
    r"|sent (from|via) \w+"
    r"|get outlook for \w+"
    r"|.*\bunsubscribe\b.*"
    r"|.*\bopt[- ]out\b.*"
    r"|you (are |have )?receiv(ed|ing) this (e-?mail|message|notification|because)\b.*"
    r"|to stop receiving these (e-?mails|messages|notifications).*"
    r"|view (this (e-?mail|message) )?in (your )?browser.*"
    r"|(manage|update|change) your (e-?mail )?(preferences|notifications|settings).*"
    r"|(©|\(c\)|copyright\s+©?)\s*\d{4}.*"
    r"|this (e-?mail|message) was sent (to|by|from)\b.*"
    r"|this is an automated (message|e-?mail|notification).*"
    r"|(please )?do not reply (to this|directly).*"
    r"|reply(ing)? to this (e-?mail|message) (is not monitored|will not).*"
    r")\s*$",
    re.I,
)

_AUTOREPLY_SUBJECT_RE = re.compile(
    r"^\s*(re\s*:\s*)?(automatic reply|auto(matic)?[-\s]?(reply|response)|"
    r"out of (the )?office|ooo\b|away from (the )?office)",
    re.I,
)
_AUTOREPLY_BODY_RE = re.compile(
    r"((i am|i'm|he is|she is|they are) (currently )?"
    r"(out of (the )?office|away from (the )?office|on (vacation|leave|pto|holiday))"
    r"|will be (out of (the )?office|away) (from|until|through)"
    r"|i will be back in the office"
    r"|thank you for your (e-?mail|message)[.,][^.]{0,120}(out of (the )?office|away))",
    re.I,
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{7,}\d)(?!\d)")
_URL_RE = re.compile(r"(https?://\S+|www\.[\w.-]+\S*)", re.I)
_TITLE_RE = re.compile(
    r"\b(ceo|cto|coo|cfo|cio|ciso|vp|svp|evp|director|manager|engineer|recruiter|"
    r"founder|co-?founder|president|architect|consultant|specialist|analyst|"
    r"partner|principal|head of|talent|sourcer)\b",
    re.I,
)

_MAX_ATTRIBUTION_CHARS = 300
_MAX_SIGNATURE_LINES = 6
_MAX_SIGNATURE_LINE_CHARS = 80


# --- template normalisation -------------------------------------------------
_TPL_MONEY_RE = re.compile(r"[$€£¥]\s?\d[\d,]*(\.\d+)?")
_TPL_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_TPL_SLASH_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_TPL_MONTH_DATE_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"[a-z]*\.?\s+\d{1,2}(st|nd|rd|th)?(,?\s*\d{4})?\b",
    re.I,
)
_TPL_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\s*([ap]\.?m\.?)?\b", re.I)
_TPL_WEEKDAY_RE = re.compile(
    r"\b(mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(day|sday|nesday|rsday|urday)?\b",
    re.I,
)
_TPL_NAME_RUN_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z'’-]+)+\b")
_TPL_ADDRESSED_NAME_RE = re.compile(
    r"\b(hi|hello|hey|dear|hiya)\s+[A-Z][\w'’-]+", re.I
)
_TPL_NUM_RE = re.compile(r"\d+")
_TPL_WS_RE = re.compile(r"\s+")

#: Length of the hex template digest. 128 bits of sha256 is ample for collapse.
TEMPLATE_ID_HEX_LEN = 32


def normalize_for_template(text: str) -> str:
    """Blank out the variable spans so machine-generated mail collapses.

    Names, dates, times, counts, money, URLs and addresses become placeholders.
    Two hundred LinkedIn digests with a name swapped normalise to one string.
    """
    normalized = _URL_RE.sub(" <url> ", text)
    normalized = _EMAIL_RE.sub(" <email> ", normalized)
    normalized = _TPL_MONEY_RE.sub(" <money> ", normalized)
    normalized = _TPL_ISO_DATE_RE.sub(" <date> ", normalized)
    normalized = _TPL_SLASH_DATE_RE.sub(" <date> ", normalized)
    normalized = _TPL_MONTH_DATE_RE.sub(" <date> ", normalized)
    normalized = _TPL_TIME_RE.sub(" <time> ", normalized)
    normalized = _TPL_WEEKDAY_RE.sub(" <weekday> ", normalized)
    normalized = _TPL_ADDRESSED_NAME_RE.sub(
        lambda m: f"{m.group(1)} <name>", normalized
    )
    normalized = _TPL_NAME_RUN_RE.sub(" <name> ", normalized)
    normalized = _PHONE_RE.sub(" <phone> ", normalized)
    normalized = _TPL_NUM_RE.sub(" <num> ", normalized)
    normalized = normalized.lower()
    return _TPL_WS_RE.sub(" ", normalized).strip()


def template_id(part: str, text: str) -> str:
    """Stable id for "this class of chunk". Empty for content-free chunks."""
    normalized = normalize_for_template(text)
    if not normalized:
        return ""
    digest = hashlib.sha256(f"{part}\x00{normalized}".encode("utf-8")).hexdigest()
    return digest[:TEMPLATE_ID_HEX_LEN]


# --- records ----------------------------------------------------------------
@dataclass(frozen=True)
class MailMessage:
    """One Gmail message, flattened to the `mail.messages` row shape."""

    message_id: str
    thread_id: str
    ts: datetime
    from_addr: str = ""
    from_name: str = ""
    to_addrs: tuple[str, ...] = ()
    cc_addrs: tuple[str, ...] = ()
    subject: str = ""
    labels: tuple[str, ...] = ()
    snippet: str = ""
    body_text: str = ""
    has_attachments: bool = False
    attachment_names: tuple[str, ...] = ()
    size_estimate: int = 0
    source_ref: str = ""
    auto_submitted: str = field(default="", compare=False)


@dataclass(frozen=True)
class MailChunk:
    """One embedding unit, or one stored-but-not-embedded span."""

    message_id: str
    thread_id: str
    ts: datetime
    seq: int
    part: str
    text: str
    char_len: int
    template_id: str

    @property
    def embeddable(self) -> bool:
        return self.part in EMBEDDABLE_PARTS


# --- segmentation -----------------------------------------------------------
def _attribution_span(lines: Sequence[str], index: int) -> int:
    """Lines consumed by an ``On <date> … wrote:`` attribution, else 0."""
    if not _ON_PREFIX_RE.match(lines[index]):
        return 0
    joined = lines[index].strip()
    for offset in range(3):
        if len(joined) > _MAX_ATTRIBUTION_CHARS:
            return 0
        if _WROTE_SUFFIX_RE.search(joined):
            return offset + 1
        if index + offset + 1 >= len(lines):
            return 0
        joined = f"{joined} {lines[index + offset + 1].strip()}"
    return 0


def _looks_like_quoted_header_block(lines: Sequence[str], index: int) -> bool:
    """Outlook pastes the original as a bare From:/Sent:/To:/Subject: block."""
    if not _FROM_HEADER_RE.match(lines[index]):
        return False
    following = lines[index + 1 : index + 5]
    return sum(1 for line in following if _HEADER_LINE_RE.match(line)) >= 2


def _consume_forward_header(lines: Sequence[str], start: int, labels: list[str | None]) -> int:
    """Label the forward marker and its header block; return the next index."""
    labels[start] = PART_FORWARD_HEADER
    index = start + 1
    seen_header = False
    while index < len(lines):
        if _HEADER_LINE_RE.match(lines[index]):
            labels[index] = PART_FORWARD_HEADER
            seen_header = True
            index += 1
            continue
        if not lines[index].strip():
            labels[index] = PART_FORWARD_HEADER
            index += 1
            if seen_header:
                break
            continue
        break
    return index


def _is_autoreply(subject: str, body: str, auto_submitted: str = "") -> bool:
    if auto_submitted and auto_submitted.strip().lower() not in {"no", ""}:
        return True
    if subject and _AUTOREPLY_SUBJECT_RE.match(subject):
        return True
    return bool(body and _AUTOREPLY_BODY_RE.search(body[:1500]))


def _classify_lines(lines: Sequence[str]) -> list[str | None]:
    labels: list[str | None] = [None] * len(lines)
    sticky: str | None = None
    index = 0
    first_content_seen = False

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if _FORWARD_MARKER_RE.match(line) or _BEGIN_FORWARD_RE.match(line):
            index = _consume_forward_header(lines, index, labels)
            sticky = PART_QUOTED
            continue

        if _ORIGINAL_MESSAGE_RE.match(line) or _looks_like_quoted_header_block(lines, index):
            labels[index] = PART_QUOTED
            sticky = PART_QUOTED
            index += 1
            continue

        span = _attribution_span(lines, index)
        if span:
            for offset in range(span):
                labels[index + offset] = PART_QUOTED
            sticky = PART_QUOTED
            index += span
            continue

        if _QUOTE_CHAR_RE.match(line):
            labels[index] = PART_QUOTED
            sticky = PART_QUOTED
            index += 1
            continue

        if _SIG_DELIM_RE.match(line) and stripped == "--":
            labels[index] = PART_SIGNATURE
            sticky = PART_SIGNATURE
            index += 1
            continue

        if stripped and len(stripped) > 20 and _DISCLAIMER_RE.search(stripped):
            labels[index] = PART_DISCLAIMER
            sticky = PART_DISCLAIMER
            index += 1
            continue

        if sticky is not None:
            labels[index] = sticky
            index += 1
            continue

        if not stripped:
            labels[index] = None
            index += 1
            continue

        if _BOILERPLATE_RE.match(stripped):
            labels[index] = PART_BOILERPLATE
            index += 1
            first_content_seen = True
            continue

        if not first_content_seen and _GREETING_RE.match(stripped):
            labels[index] = PART_GREETING
            first_content_seen = True
            index += 1
            continue

        if _SIGNOFF_RE.match(stripped):
            labels[index] = PART_GREETING
            index += 1
            # A bare name directly under the sign-off belongs with it.
            probe = index
            while probe < len(lines) and not lines[probe].strip():
                probe += 1
            if (
                probe < len(lines)
                and probe - index <= 1
                and _NAME_LINE_RE.match(lines[probe].strip())
                and len(lines[probe].strip()) <= 40
            ):
                for blank in range(index, probe):
                    labels[blank] = PART_GREETING
                labels[probe] = PART_GREETING
                index = probe + 1
            first_content_seen = True
            continue

        labels[index] = PART_BODY
        first_content_seen = True
        index += 1

    return labels


def _apply_trailing_signature_heuristic(lines: Sequence[str], labels: list[str | None]) -> None:
    """A trailing contact block with no ``--`` delimiter is still a signature.

    Conservative on purpose: the block must be separated from the prose by a
    blank line, be short, and carry a contact marker. Consent is the labeler —
    a wrong call here is a training example, not a corruption.
    """
    end = len(labels)
    while end > 0 and (labels[end - 1] is None or not lines[end - 1].strip()):
        end -= 1
    if end == 0 or labels[end - 1] != PART_BODY:
        return

    region_start = end
    while region_start > 0 and labels[region_start - 1] in (PART_BODY, None):
        region_start -= 1

    block_start = region_start
    for index in range(region_start, end):
        if not lines[index].strip():
            block_start = index + 1
    if block_start <= region_start or block_start >= end:
        return
    if not any(lines[index].strip() for index in range(region_start, block_start)):
        return

    run = [lines[index] for index in range(block_start, end) if lines[index].strip()]
    if not run or len(run) > _MAX_SIGNATURE_LINES:
        return
    if any(len(line.strip()) > _MAX_SIGNATURE_LINE_CHARS for line in run):
        return
    blob = "\n".join(run)
    if not (_EMAIL_RE.search(blob) or _PHONE_RE.search(blob) or _TITLE_RE.search(blob)):
        return
    for index in range(block_start, end):
        if labels[index] in (PART_BODY, None):
            labels[index] = PART_SIGNATURE


def _merge_spans(lines: Sequence[str], labels: Sequence[str | None]) -> list[tuple[str, str]]:
    spans: list[tuple[str, list[str]]] = []
    for line, label in zip(lines, labels):
        if label is None:
            if spans:
                spans[-1][1].append(line)
            continue
        if spans and spans[-1][0] == label:
            spans[-1][1].append(line)
        else:
            spans.append((label, [line]))

    merged: list[tuple[str, str]] = []
    for label, body in spans:
        text = "\n".join(body).strip("\n").rstrip()
        if text.strip():
            merged.append((label, text))
    return merged


def _split_body(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if size and size + len(paragraph) + 2 > max_chars:
            pieces.append("\n\n".join(current))
            current, size = [], 0
        if len(paragraph) > max_chars:
            if current:
                pieces.append("\n\n".join(current))
                current, size = [], 0
            for start in range(0, len(paragraph), max_chars):
                pieces.append(paragraph[start : start + max_chars])
            continue
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        pieces.append("\n\n".join(current))
    return [piece for piece in pieces if piece.strip()] or [text]


def segment_text(
    subject: str,
    body: str,
    *,
    auto_submitted: str = "",
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
) -> list[tuple[str, str]]:
    """Segment a message into ``(part, text)`` pairs in document order.

    Nothing is discarded — every span of the original body appears under some
    part. Only ``subject`` and ``body`` are marked for embedding downstream.
    """
    result: list[tuple[str, str]] = []
    subject_text = (subject or "").strip()
    if subject_text:
        result.append((PART_SUBJECT, subject_text))

    body_text = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    if not body_text.strip():
        return result

    lines = body_text.split("\n")
    labels = _classify_lines(lines)
    _apply_trailing_signature_heuristic(lines, labels)

    autoreply = _is_autoreply(subject_text, body_text, auto_submitted)
    if autoreply:
        labels = [PART_AUTOREPLY if label == PART_BODY else label for label in labels]

    for part, text in _merge_spans(lines, labels):
        if part == PART_BODY:
            for piece in _split_body(text, max_body_chars):
                result.append((PART_BODY, piece))
        else:
            result.append((part, text))
    return result


def segment_message(
    message: MailMessage,
    *,
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
) -> list[MailChunk]:
    """Chunk one message at ingest. Chunk boundaries are a property of the
    document, so they must not drift between embedding runs."""
    pairs = segment_text(
        message.subject,
        message.body_text,
        auto_submitted=message.auto_submitted,
        max_body_chars=max_body_chars,
    )
    return [
        MailChunk(
            message_id=message.message_id,
            thread_id=message.thread_id,
            ts=message.ts,
            seq=seq,
            part=part,
            text=text,
            char_len=len(text),
            template_id=template_id(part, text),
        )
        for seq, (part, text) in enumerate(pairs)
    ]


def segment_messages(
    messages: Iterable[MailMessage],
    *,
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
) -> list[MailChunk]:
    chunks: list[MailChunk] = []
    for message in messages:
        chunks.extend(segment_message(message, max_body_chars=max_body_chars))
    return chunks


def part_histogram(chunks: Iterable[MailChunk]) -> dict[str, int]:
    """Counts per part — the cheap way to see whether the chunker is sane."""
    histogram = {part: 0 for part in PARTS}
    for chunk in chunks:
        histogram[chunk.part] = histogram.get(chunk.part, 0) + 1
    return histogram


def embeddable_exemplars(chunks: Iterable[MailChunk]) -> list[MailChunk]:
    """One exemplar per (part, template_id) among embeddable chunks.

    Instances keep their rows in ``mail.chunks`` — full fidelity, nothing lost —
    but only the exemplar is worth a vector.
    """
    seen: set[tuple[str, str]] = set()
    exemplars: list[MailChunk] = []
    for chunk in chunks:
        if not chunk.embeddable:
            continue
        key = (chunk.part, chunk.template_id)
        if chunk.template_id and key in seen:
            continue
        seen.add(key)
        exemplars.append(chunk)
    return exemplars
