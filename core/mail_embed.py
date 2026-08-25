"""Text embeddings for the mail corpus — the audio-app pattern, in Python.

Follows ``audio-app/lib/embed-client.ts`` deliberately and closely, because that
client already paid for the lessons this one would otherwise have to relearn:

* The service is **odin llama-swap**, OpenAI-compatible at ``/v1/embeddings``.
  Reached over internal DNS (``odin.ravenmask.net``), never a tailnet IP.
* The deployed model caps each request at a **fixed token batch** (observed 512
  tokens). Windows are therefore sized in *characters* well under it — 1400
  chars is roughly 370 tokens, which leaves headroom for token-dense text.
* Any window that still overflows is **split adaptively and mean-pooled**, so a
  change in the server's real limit degrades quality slightly instead of
  hard-failing an ingest.

Two subtleties are carried over verbatim from that client, both of which are
bugs if you re-derive them casually:

1. Overlap on an adaptive split is capped at a **quarter** of the text, so each
   half is strictly smaller than its parent. A fixed overlap can make a half
   equal to the parent for short windows (201..300 chars at overlap 150) and
   recurse forever.
2. Only *size* errors trigger a split. Network and auth errors bubble up —
   silently mean-pooling around a down service would poison the corpus.

Nothing here writes to ClickHouse; see ``MailEmbeddingWriter`` for that, which
reuses the same idempotent client as the rest of the Stage.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_EMBED_API_URL = "http://odin.ravenmask.net:18090"
DEFAULT_EMBED_MODEL = "nomic-embed-text"

#: ~370 tokens of token-dense text against an observed 512-token batch cap.
DEFAULT_MAX_WINDOW_CHARS = 1400
DEFAULT_WINDOW_OVERLAP = 150
#: Floor for adaptive splitting; below this a "too large" error is real.
MIN_WINDOW_CHARS = 200

DEFAULT_TIMEOUT_SECONDS = 120.0

#: The corpus label written into the shared embeddings row shape.
DEFAULT_CORPUS = "mail"

_TOO_LARGE_RE = re.compile(
    r"too large|exceeds|context length|batch size|maximum context|\b413\b",
    re.IGNORECASE,
)


class MailEmbedError(RuntimeError):
    """The embedding service failed in a way the caller must handle."""


class MailEmbedConfigError(RuntimeError):
    """Configuration is missing or malformed. Carries no secret values."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    """Ignore unset/NaN/<=0 and fall back — same contract as ``envInt`` there."""
    raw = env.get(key)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class EmbedConfig:
    """Where the embedding service is and how to chunk for it."""

    url: str = DEFAULT_EMBED_API_URL
    model: str = DEFAULT_EMBED_MODEL
    max_window_chars: int = DEFAULT_MAX_WINDOW_CHARS
    window_overlap: int = DEFAULT_WINDOW_OVERLAP
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not str(self.url).strip():
            raise MailEmbedConfigError("mail_embed_missing_url")
        if not str(self.model).strip():
            raise MailEmbedConfigError("mail_embed_missing_model")
        if self.max_window_chars <= MIN_WINDOW_CHARS:
            raise MailEmbedConfigError("mail_embed_window_too_small")
        if self.window_overlap >= self.max_window_chars:
            raise MailEmbedConfigError("mail_embed_overlap_exceeds_window")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "EmbedConfig":
        env = environ if environ is not None else os.environ
        return cls(
            url=(env.get("EMBED_API_URL") or DEFAULT_EMBED_API_URL).strip().rstrip("/"),
            model=(env.get("EMBED_MODEL") or DEFAULT_EMBED_MODEL).strip(),
            max_window_chars=_env_int(env, "EMBED_MAX_WINDOW_CHARS", DEFAULT_MAX_WINDOW_CHARS),
            window_overlap=_env_int(env, "EMBED_WINDOW_OVERLAP", DEFAULT_WINDOW_OVERLAP),
            timeout_seconds=float(
                _env_int(env, "EMBED_TIMEOUT_SECONDS", int(DEFAULT_TIMEOUT_SECONDS))
            ),
        )

    def describe(self) -> str:
        """Safe to print — this service takes no credentials."""
        return f"{self.url} model={self.model} window={self.max_window_chars}"


def is_too_large_error(error: BaseException | str) -> bool:
    """Did the service reject the input for *size*, as opposed to failing?

    Only size errors may be split-and-pooled around; everything else is a real
    failure and must reach the caller.
    """
    message = str(error)
    return bool(_TOO_LARGE_RE.search(message))


def _mean_pool(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        raise MailEmbedError("mean_pool_of_no_vectors")
    dim = len(vectors[0])
    out = [0.0] * dim
    for vector in vectors:
        if len(vector) != dim:
            raise MailEmbedError(
                f"embed_window_dim_mismatch ({len(vector)} vs {dim})"
            )
        for index, value in enumerate(vector):
            out[index] += float(value)
    count = float(len(vectors))
    return [value / count for value in out]


def windows(text: str, *, size: int, overlap: int) -> list[str]:
    """Split ``text`` into overlapping windows of at most ``size`` characters."""
    body = text or ""
    if len(body) <= size:
        return [body] if body else []
    stride = max(1, size - overlap)
    out: list[str] = []
    start = 0
    while start < len(body):
        out.append(body[start : start + size])
        if start + size >= len(body):
            break
        start += stride
    return out


class MailEmbedder:
    """Embeds text against the llama-swap service. ``client`` is injected."""

    def __init__(self, *, config: EmbedConfig, client: Any) -> None:
        self._config = config
        self._client = client

    @property
    def config(self) -> EmbedConfig:
        return self._config

    def embed_text(self, text: str) -> list[float]:
        """One request, one vector. Raises on any non-2xx."""
        response = self._client.post(
            f"{self._config.url}/v1/embeddings",
            json={"model": self._config.model, "input": text},
            headers={"content-type": "application/json"},
            timeout=self._config.timeout_seconds,
        )
        if response.status_code >= 400:
            raise MailEmbedError(
                f"embed API {response.status_code}: {response.text[:200]}"
            )
        payload = response.json()
        data = payload.get("data") if isinstance(payload, Mapping) else None
        if not data or not isinstance(data, list):
            raise MailEmbedError("embed API: missing data[0].embedding")
        vector = data[0].get("embedding") if isinstance(data[0], Mapping) else None
        if not isinstance(vector, list) or not vector:
            raise MailEmbedError("embed API: missing data[0].embedding")
        return [float(value) for value in vector]

    def _embed_window(self, text: str) -> list[float]:
        """Embed one window, splitting adaptively if the service says too large."""
        try:
            return self.embed_text(text)
        except MailEmbedError as error:
            if not is_too_large_error(error) or len(text) <= MIN_WINDOW_CHARS:
                raise
            midpoint = len(text) // 2
            # Cap overlap at a quarter of the text so each half is STRICTLY
            # smaller than the parent (<= 3/4 length). A fixed overlap could make
            # a half equal the parent for short windows -> infinite recursion.
            overlap = min(self._config.window_overlap, len(text) // 4)
            left = text[: midpoint + overlap]
            right = text[max(0, midpoint - overlap) :]
            return _mean_pool([self._embed_window(left), self._embed_window(right)])

    def embed_long_text(self, text: str) -> list[float]:
        """Embed text of any length, mean-pooling across windows."""
        body = (text or "").strip()
        if not body:
            raise MailEmbedError("embed_empty_text")
        parts = windows(
            body,
            size=self._config.max_window_chars,
            overlap=self._config.window_overlap,
        )
        if len(parts) == 1:
            return self._embed_window(parts[0])
        return _mean_pool([self._embed_window(part) for part in parts])


# --- ClickHouse row shaping -------------------------------------------------
def embedding_row(
    *,
    doc_id: str,
    seq: int,
    ts: Any,
    role: str,
    text: str,
    embedding: Sequence[float],
    model: str,
    corpus: str = DEFAULT_CORPUS,
) -> dict[str, Any]:
    """One row in the shared ``embeddings`` shape (same as forensics.embeddings)."""
    from core.mail_clickhouse import format_datetime

    return {
        "corpus": corpus,
        "doc_id": doc_id,
        "seq": int(seq),
        "ts": format_datetime(ts) if hasattr(ts, "astimezone") else ts,
        "role": role,
        "text": text,
        "embedding": [float(value) for value in embedding],
        "model": model,
    }


def embeddable_chunks(chunks: Iterable[Any]) -> list[Any]:
    """The chunks the taxonomy says carry signal — subject and body only.

    Everything else (signatures, greetings, quoted replies, disclaimers,
    autoreplies, tracking cruft) is stored in full fidelity but never embedded;
    that separation is the whole point of defining raw vs chunked at ingest.
    """
    return [chunk for chunk in chunks if getattr(chunk, "embeddable", False)]
