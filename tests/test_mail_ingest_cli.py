"""CLI surface for the mail corpus backfill — refuse loudly, print safely."""
from __future__ import annotations

import pytest

from cli.ingest_mail_corpus import build_parser, main
from core.mail_clickhouse import DEFAULT_DATABASE

_CLICKHOUSE_ENV = (
    "MAIL_CLICKHOUSE_URL",
    "MAIL_CLICKHOUSE_USER",
    "MAIL_CLICKHOUSE_PASSWORD",
    "MAIL_CLICKHOUSE_DATABASE",
    "MAIL_CLICKHOUSE_ALLOW_EMPTY_PASSWORD",
    "MAIL_CLICKHOUSE_TIMEOUT",
    "MAIL_CORPUS_QUERY",
)


@pytest.fixture(autouse=True)
def clean_clickhouse_env(monkeypatch):
    for name in _CLICKHOUSE_ENV:
        monkeypatch.delenv(name, raising=False)


class TestParser:
    def test_defaults_are_the_three_year_window(self):
        args = build_parser().parse_args([])
        assert args.years == 3
        assert args.dry_run is False
        assert args.force is False

    def test_dangerous_flags_are_opt_in(self):
        args = build_parser().parse_args([])
        assert args.include_spam_trash is False
        assert args.init_schema is False


class TestPrintDdl:
    def test_prints_the_schema_without_touching_a_server(self, capsys):
        assert main(["--print-ddl"]) == 0
        out = capsys.readouterr().out
        assert f"CREATE DATABASE IF NOT EXISTS {DEFAULT_DATABASE}" in out
        assert "ReplacingMergeTree(ingested_at)" in out
        assert out.count("CREATE TABLE IF NOT EXISTS") == 3

    def test_respects_the_configured_database(self, monkeypatch, capsys):
        monkeypatch.setenv("MAIL_CLICKHOUSE_DATABASE", "mail_dev")
        assert main(["--print-ddl"]) == 0
        assert "mail_dev.messages" in capsys.readouterr().out


class TestCredentialRefusal:
    def test_missing_clickhouse_user_refuses_with_a_reason_code(self, capsys):
        assert main(["--max-messages", "1"]) == 2
        err = capsys.readouterr().err
        assert "mail_clickhouse_user_missing" in err
        assert "there is no default" in err

    def test_missing_gmail_credentials_refuse_after_config(self, monkeypatch, capsys):
        monkeypatch.setenv("MAIL_CLICKHOUSE_USER", "mail_ingest")
        monkeypatch.setenv("MAIL_CLICKHOUSE_PASSWORD", "pw")
        for name in ("GMAIL_ACCESS_TOKEN", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
            monkeypatch.delenv(name, raising=False)
        assert main(["--dry-run", "--max-messages", "1"]) == 2
        assert "gmail_credentials_missing" in capsys.readouterr().err

    def test_dry_run_alone_does_not_require_clickhouse(self, monkeypatch, capsys):
        for name in ("GMAIL_ACCESS_TOKEN", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
            monkeypatch.delenv(name, raising=False)
        # It gets past ClickHouse config and stops on Gmail auth instead.
        assert main(["--dry-run"]) == 2
        assert "mail_clickhouse_user_missing" not in capsys.readouterr().err
