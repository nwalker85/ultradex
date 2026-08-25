"""Embeddings — window discipline, adaptive splitting, and row shape.

The interesting tests here are the ones about *failure*: the embedding service
caps each request at a fixed token batch, and the two ways to get that wrong
(recursing forever, or silently pooling around a dead service) are both
tempting. audio-app's client hit both; this suite pins them shut.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.mail_clickhouse import EMBEDDINGS_TABLE, schema_statements
from core.mail_corpus import DEFAULT_MAX_BODY_CHARS, MailMessage, segment_message
from core.mail_embed import (
    DEFAULT_EMBED_API_URL,
    DEFAULT_EMBED_MODEL,
    DEFAULT_MAX_WINDOW_CHARS,
    DEFAULT_WINDOW_OVERLAP,
    MIN_WINDOW_CHARS,
    EmbedConfig,
    MailEmbedConfigError,
    MailEmbedder,
    MailEmbedError,
    embeddable_chunks,
    embedding_row,
    is_too_large_error,
    windows,
)

TS = datetime(2026, 8, 24, 14, 30, 0, 250000, tzinfo=timezone.utc)


def _message(subject: str, body: str) -> MailMessage:
    return MailMessage(
        message_id="m", thread_id="t", ts=TS,
        from_addr="dana@acme.example", from_name="Dana Whitfield",
        to_addrs=("nate@example.com",), subject=subject, body_text=body,
        source_ref="gmail:1",
    )


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class FakeEmbedClient:
    """Returns a fixed-dimension vector, or fails per a scripted rule."""

    def __init__(self, *, dim: int = 4, fail_over: int | None = None) -> None:
        self.dim = dim
        self.fail_over = fail_over
        self.inputs: list[str] = []

    def post(self, url, *, json=None, headers=None, timeout=None):
        text = (json or {}).get("input", "")
        self.inputs.append(text)
        if self.fail_over is not None and len(text) > self.fail_over:
            return FakeResponse(
                status_code=400,
                text="input is too large for the configured batch size",
            )
        # A vector whose first component encodes the length, so mean-pooling is
        # observable rather than a black box.
        vector = [float(len(text))] + [1.0] * (self.dim - 1)
        return FakeResponse(payload={"data": [{"embedding": vector}]})


def _embedder(**kwargs) -> tuple[MailEmbedder, FakeEmbedClient]:
    client = kwargs.pop("client", None) or FakeEmbedClient()
    config = EmbedConfig(url="http://embed.example:18090", model="test-model", **kwargs)
    return MailEmbedder(config=config, client=client), client


class TestConfig:
    def test_defaults_point_at_odin_over_internal_dns_not_a_tailnet_ip(self):
        config = EmbedConfig.from_env({})
        assert config.url == DEFAULT_EMBED_API_URL
        assert "odin.ravenmask.net" in config.url
        assert not any(char.isdigit() for char in config.url.split("//")[1].split(":")[0])
        assert config.model == DEFAULT_EMBED_MODEL

    def test_everything_is_overridable_from_env(self):
        config = EmbedConfig.from_env(
            {
                "EMBED_API_URL": "http://other:18090/",
                "EMBED_MODEL": "another-model",
                "EMBED_MAX_WINDOW_CHARS": "900",
                "EMBED_WINDOW_OVERLAP": "80",
            }
        )
        assert (config.url, config.model) == ("http://other:18090", "another-model")
        assert (config.max_window_chars, config.window_overlap) == (900, 80)

    def test_garbage_window_values_fall_back_rather_than_crash(self):
        config = EmbedConfig.from_env(
            {"EMBED_MAX_WINDOW_CHARS": "not-a-number", "EMBED_WINDOW_OVERLAP": "-5"}
        )
        assert config.max_window_chars == DEFAULT_MAX_WINDOW_CHARS
        assert config.window_overlap == DEFAULT_WINDOW_OVERLAP

    def test_overlap_may_not_swallow_the_window(self):
        with pytest.raises(MailEmbedConfigError):
            EmbedConfig(max_window_chars=500, window_overlap=500)

    def test_window_may_not_be_smaller_than_the_split_floor(self):
        with pytest.raises(MailEmbedConfigError):
            EmbedConfig(max_window_chars=MIN_WINDOW_CHARS)


class TestChunkerAgreesWithEmbedder:
    def test_body_chunks_are_sized_to_fit_the_embedding_window(self):
        """A chunk IS an embedding unit, so it must fit one without pooling.

        If these drift apart, every long body silently becomes a mean-pooled
        (blurrier) vector instead of a real one, and nothing fails to warn you.
        """
        assert DEFAULT_MAX_BODY_CHARS <= DEFAULT_MAX_WINDOW_CHARS

    def test_a_real_long_body_produces_only_single_window_chunks(self):
        body = "\n\n".join(f"Paragraph {i}. " + ("filler words " * 40) for i in range(12))
        chunks = segment_message(_message("Long one", body))
        for chunk in embeddable_chunks(chunks):
            assert len(windows(
                chunk.text,
                size=DEFAULT_MAX_WINDOW_CHARS,
                overlap=DEFAULT_WINDOW_OVERLAP,
            )) == 1


class TestWindows:
    def test_short_text_is_one_window(self):
        assert windows("hello", size=100, overlap=10) == ["hello"]

    def test_empty_text_is_no_windows(self):
        assert windows("", size=100, overlap=10) == []

    def test_long_text_is_split_with_overlap_and_covers_everything(self):
        text = "".join(str(i % 10) for i in range(1000))
        parts = windows(text, size=300, overlap=50)
        assert len(parts) > 1
        assert all(len(part) <= 300 for part in parts)
        assert parts[0][0] == text[0] and text.endswith(parts[-1][-1])
        # Consecutive windows overlap, so no boundary token is orphaned.
        assert parts[1].startswith(text[250:260])


class TestEmbedText:
    def test_happy_path_returns_the_vector(self):
        embedder, client = _embedder()
        vector = embedder.embed_text("hello")
        assert vector == [5.0, 1.0, 1.0, 1.0]
        assert client.inputs == ["hello"]

    def test_http_error_is_surfaced_with_the_status(self):
        embedder, _ = _embedder(
            client=FakeEmbedClient(fail_over=0),
        )
        with pytest.raises(MailEmbedError) as exc:
            embedder.embed_text("anything")
        assert "400" in str(exc.value)

    def test_malformed_payload_is_refused(self):
        class Empty(FakeEmbedClient):
            def post(self, url, *, json=None, headers=None, timeout=None):
                return FakeResponse(payload={"data": []})

        embedder, _ = _embedder(client=Empty())
        with pytest.raises(MailEmbedError):
            embedder.embed_text("x")


class TestTooLargeClassification:
    @pytest.mark.parametrize(
        "message",
        [
            "input is too large",
            "exceeds the maximum context",
            "context length exceeded",
            "batch size too small for input",
            "HTTP 413 payload",
        ],
    )
    def test_size_errors_are_recognised(self, message):
        assert is_too_large_error(message)

    @pytest.mark.parametrize(
        "message",
        ["connection refused", "embed API 500: internal", "name resolution failed", "401"],
    )
    def test_other_failures_are_not_size_errors(self, message):
        assert not is_too_large_error(message)


class TestAdaptiveSplitting:
    def test_oversized_window_is_split_and_mean_pooled(self):
        # Service accepts <= 300 chars; give it 500 in a single window.
        embedder, client = _embedder(
            max_window_chars=1000,
            window_overlap=20,
            client=FakeEmbedClient(fail_over=300),
        )
        vector = embedder.embed_long_text("x" * 500)
        assert len(vector) == 4
        # It retried smaller pieces rather than giving up.
        assert any(len(text) <= 300 for text in client.inputs)
        assert max(len(text) for text in client.inputs) == 500

    def test_splitting_terminates_and_does_not_recurse_forever(self):
        """The overlap cap is what makes each half strictly smaller.

        With a fixed overlap of 150, a 260-char window would split into two
        260-char halves and spin until the stack died.
        """
        embedder, client = _embedder(
            max_window_chars=1000,
            window_overlap=150,
            client=FakeEmbedClient(fail_over=200),
        )
        vector = embedder.embed_long_text("y" * 260)
        assert len(vector) == 4
        # Terminated quickly, and every retry was STRICTLY smaller than 260.
        assert len(client.inputs) < 10
        retries = [len(text) for text in client.inputs[1:]]
        assert retries and all(length < 260 for length in retries)

    def test_a_split_that_cannot_get_small_enough_raises_at_the_floor(self):
        embedder, client = _embedder(
            max_window_chars=1000,
            window_overlap=150,
            client=FakeEmbedClient(fail_over=50),
        )
        with pytest.raises(MailEmbedError) as exc:
            embedder.embed_long_text("y" * 260)
        assert "too large" in str(exc.value)
        assert len(client.inputs) < 10

    def test_non_size_errors_bubble_up_instead_of_being_pooled_around(self):
        class Dead(FakeEmbedClient):
            def post(self, url, *, json=None, headers=None, timeout=None):
                self.inputs.append((json or {}).get("input", ""))
                return FakeResponse(status_code=503, text="upstream connect error")

        embedder, client = _embedder(client=Dead())
        with pytest.raises(MailEmbedError) as exc:
            embedder.embed_long_text("z" * 5000)
        assert "503" in str(exc.value)
        # One attempt per window, no doubling from split retries.
        assert all("connect" not in text for text in client.inputs)

    def test_multi_window_text_is_mean_pooled_across_windows(self):
        embedder, client = _embedder(max_window_chars=300, window_overlap=0)
        vector = embedder.embed_long_text("a" * 900)
        # Three 300-char windows; first component encodes length.
        assert len(client.inputs) == 3
        assert vector[0] == pytest.approx(300.0)

    def test_empty_text_is_refused_rather_than_embedded(self):
        embedder, _ = _embedder()
        with pytest.raises(MailEmbedError):
            embedder.embed_long_text("   ")


class TestOnlySignalIsEmbedded:
    def test_signatures_and_quotes_are_stored_but_never_embedded(self):
        body = (
            "Hi Nate,\n\nAre you free Tuesday?\n\n"
            "Best,\nDana\n\n"
            "--\nDana Whitfield | Acme | (555) 010-0000\n\n"
            "> On Mon, Nate wrote:\n> Sounds good.\n"
        )
        chunks = segment_message(_message("Technical screen", body))
        embedded = embeddable_chunks(chunks)
        assert len(embedded) < len(chunks), "everything was embedded; taxonomy did nothing"
        assert {chunk.part for chunk in embedded} <= {"subject", "body"}
        joined = "\n".join(chunk.text for chunk in embedded)
        assert "555" not in joined and "> On Mon" not in joined


class TestRowShape:
    def test_row_matches_the_embeddings_table_columns(self):
        row = embedding_row(
            doc_id="msg-1", seq=0, ts=TS, role="body", text="hello",
            embedding=[0.1, 0.2], model="nomic-embed-text",
        )
        assert set(row) == {
            "corpus", "doc_id", "seq", "ts", "role", "text", "embedding", "model",
        }
        ddl = [s for s in schema_statements() if f".{EMBEDDINGS_TABLE}" in s][0]
        for column in row:
            assert column in ddl

    def test_timestamps_are_normalised_to_utc_iso(self):
        row = embedding_row(
            doc_id="d", seq=1, ts=TS, role="subject", text="t",
            embedding=[1.0], model="m",
        )
        assert row["ts"] == "2026-08-24T14:30:00.250Z"

    def test_corpus_defaults_to_mail_so_it_can_share_a_table(self):
        row = embedding_row(
            doc_id="d", seq=0, ts=TS, role="body", text="t",
            embedding=[1.0], model="m",
        )
        assert row["corpus"] == "mail"
