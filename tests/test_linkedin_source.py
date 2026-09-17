"""LinkedIn source: list parsing, ranking, payload, idempotency. Synthetic names
only; no network — the bridge is faked."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx

from core.linkedin_owed_replies import TASK_ID_PREFIX, TASK_SOURCE, plan_sync, rank, task_id_for, task_payload
from core.linkedin_reads import (
    BridgeUnavailable,
    ChromeBridge,
    LinkedInInbox,
    LinkedInThread,
    parse_time_label,
    rows_to_threads,
)
from core.owed_replies import CccContactDirectory, ContactRow

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=timezone.utc)

ROWS = [
    ContactRow(id="c-ada", name="Ada Quill", email=None, company="Northwind Analytics"),
    ContactRow(id="c-bulk", name="Advance Auto Parts", email=None),
]

# What the scan returns: no URLs (LinkedIn's rows carry none); `i` is the row index.
LIST_ROWS = [
    {"i": 0, "name": "Ada Quill", "time": "Sep 14", "snippet": "Ada: Thanks for connecting, are you open to a call", "unread": True},
    {"i": 1, "name": "Bram Holt", "time": "1:02 PM", "snippet": "You: Taking you up on the open door.", "unread": False},
    {"i": 2, "name": "Cy Marlow", "time": "Sep 10", "snippet": "Cy: Individual contributor roles might be available", "unread": False},
    {"i": 3, "name": "LinkedIn", "time": "Sep 16", "snippet": "Sponsored: Grow your network", "unread": True},
    {"i": 4, "name": "Dee Voss", "time": "Sep 17", "snippet": "Dee: Sent you the deck", "unread": True},
]
PATHS = {0: "/messaging/thread/2-abc/", 1: "/messaging/thread/2-def/", 2: "/messaging/thread/2-ghi/", 3: "/messaging/thread/2-sys/", 4: "/messaging/thread/2-jkl/"}
ROWS_WITH_PATHS = [dict(r, path=PATHS[r["i"]]) for r in LIST_ROWS]


def _hex(path: str) -> str:
    return "-".join(format(ord(c), "x") for c in path)


def test_parse_time_label_today_and_dates():
    assert parse_time_label("1:17 PM", now=NOW) == NOW.replace(hour=13, minute=17)
    assert parse_time_label("Sep 14", now=NOW) == datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    assert parse_time_label("Mar 3, 2025", now=NOW) == datetime(2025, 3, 3, 12, 0, tzinfo=timezone.utc)
    assert parse_time_label("Dec 30", now=NOW).year == 2025  # in the future this year -> last year
    assert parse_time_label("weird", now=NOW) == NOW


def test_rows_to_threads_direction_and_url():
    threads = rows_to_threads(ROWS_WITH_PATHS, now=NOW)
    by_name = {t.counterparty: t for t in threads}
    assert by_name["Ada Quill"].last_message_from == "them"
    assert by_name["Ada Quill"].last_message_text == "Thanks for connecting, are you open to a call"
    assert by_name["Bram Holt"].last_message_from == "me"
    assert by_name["Bram Holt"].last_message_text == "Taking you up on the open door."
    assert by_name["Ada Quill"].thread_url == "https://www.linkedin.com/messaging/thread/2-abc/"
    assert by_name["LinkedIn"].is_system


def test_rank_owed_grace_and_system():
    threads = rows_to_threads(ROWS_WITH_PATHS, now=NOW)
    directory = CccContactDirectory.from_rows(ROWS)
    ranked = {r.thread.counterparty: r for r in rank(threads, directory=directory, now=NOW)}
    assert ranked["Ada Quill"].owed and ranked["Ada Quill"].known
    assert not ranked["Bram Holt"].owed and ranked["Bram Holt"].reason == "you wrote last"
    assert ranked["Cy Marlow"].owed and not ranked["Cy Marlow"].known  # 7d > cold grace
    assert not ranked["LinkedIn"].owed and ranked["LinkedIn"].reason == "system sender"
    assert not ranked["Dee Voss"].owed  # today, within grace


def test_task_payload_shape():
    threads = rows_to_threads(ROWS_WITH_PATHS, now=NOW)
    directory = CccContactDirectory.from_rows(ROWS)
    ada = [r for r in rank(threads, directory=directory, now=NOW) if r.thread.counterparty == "Ada Quill"][0]
    payload = task_payload(ada, directory=directory)
    assert payload["id"].startswith(TASK_ID_PREFIX) and len(payload["id"]) == len(TASK_ID_PREFIX) + 16
    assert payload["source"] == TASK_SOURCE == "ccc_linkedin"
    assert payload["suggested_action"] == "reply"
    assert payload["title"].startswith("Reply on LinkedIn to Ada Quill: Thanks for connecting")
    assert payload["contact_id"] == "c-ada" and payload["organization_name"] == "Northwind Analytics"
    assert payload["raw_metadata"]["relay"] == "linkedin"
    assert payload["raw_metadata"]["reply_url"] == "https://www.linkedin.com/messaging/thread/2-abc/"
    assert "Sep 14" in payload["description"] and "3 days" in payload["description"]
    assert json.dumps(payload)  # serialisable


def test_task_id_changes_with_new_inbound_message():
    a = LinkedInThread("Ada Quill", "https://www.linkedin.com/messaging/thread/2-abc/", "hi", "them", NOW - timedelta(days=3))
    b = LinkedInThread("Ada Quill", "https://www.linkedin.com/messaging/thread/2-abc/", "again", "them", NOW - timedelta(days=1))
    assert task_id_for(a) != task_id_for(b)
    assert task_id_for(a) == task_id_for(a)


def test_task_id_stable_whether_or_not_the_url_resolved():
    # A DOM click can fail on one scan and succeed on the next; the id must not move.
    unresolved = LinkedInThread("Ada Quill", "", "hi", "them", NOW - timedelta(days=3))
    resolved = unresolved.with_url("https://www.linkedin.com/messaging/thread/2-abc/")
    assert task_id_for(unresolved) == task_id_for(resolved)
    # ...and a second scan that sees the same message under the resolved URL is a skip, not a create.
    directory = CccContactDirectory.from_rows(ROWS)
    ranked = rank([resolved], directory=directory, now=NOW)
    existing = {task_id_for(unresolved): {"status": "pending", "thread_url": "", "contact_name": "Ada Quill"}}
    plan = plan_sync(ranked, directory=directory, existing=existing)
    assert plan.create == [] and plan.skipped == [task_id_for(unresolved)]


def test_plan_sync_idempotent_and_closes_answered():
    threads = rows_to_threads(ROWS_WITH_PATHS, now=NOW)
    directory = CccContactDirectory.from_rows(ROWS)
    ranked = rank(threads, directory=directory, now=NOW)
    first = plan_sync(ranked, directory=directory, existing={})
    assert {p["contact_name"] for p in first.create} == {"Ada Quill", "Cy Marlow"}
    existing = {p["id"]: {"status": "pending", "thread_url": p["raw_metadata"]["thread_url"], "contact_name": p["contact_name"]} for p in first.create}
    # An older open task on Bram's thread; Bram's thread now has Nate writing last -> close it.
    existing["ccc-linkedin-oldbram000000000"] = {"status": "pending", "thread_url": "https://www.linkedin.com/messaging/thread/2-def/", "contact_name": "Bram Holt"}
    second = plan_sync(ranked, directory=directory, existing=existing)
    assert second.create == []
    assert sorted(second.skipped) == sorted(existing_id for existing_id in existing if existing_id != "ccc-linkedin-oldbram000000000")
    assert second.close == ["ccc-linkedin-oldbram000000000"]


def test_plan_sync_closes_by_name_when_scan_has_no_url():
    threads = rows_to_threads(LIST_ROWS, now=NOW)  # no URLs, as the scan returns them
    directory = CccContactDirectory.from_rows(ROWS)
    ranked = rank(threads, directory=directory, now=NOW)
    existing = {"ccc-linkedin-oldbram000000000": {"status": "pending", "thread_url": "https://www.linkedin.com/messaging/thread/2-def/", "contact_name": "Bram Holt"}}
    plan = plan_sync(ranked, directory=directory, existing=existing)
    assert plan.close == ["ccc-linkedin-oldbram000000000"]
    # Owed rows without a resolved URL still get a stable id and the messaging root as reply_url.
    ada = [p for p in plan.create if p["contact_name"] == "Ada Quill"][0]
    assert ada["raw_metadata"]["thread_url"] == "" and ada["raw_metadata"]["reply_url"] == "https://www.linkedin.com/messaging/"
    assert ada["id"] == task_id_for(threads[0])


class _FakeBridgeTransport(httpx.BaseTransport):
    """Answers the MCP handshake and returns canned tool results."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.initialized = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        method = body.get("method")
        if method == "ping":
            if request.headers.get("mcp-session-id") == "sid-1":
                return httpx.Response(200, headers={"mcp-session-id": "sid-1"}, json={"jsonrpc": "2.0", "id": 0, "result": {}})
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 0, "error": {"code": -32000, "message": "no session"}})
        if method == "initialize":
            self.initialized += 1
            if self.initialized > 1:
                return httpx.Response(500, json={"statusCode": 500, "message": "Already connected to a transport"})
            return httpx.Response(200, headers={"mcp-session-id": "sid-1"}, json={"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "fake"}}})
        if method == "notifications/initialized":
            return httpx.Response(202, headers={"mcp-session-id": "sid-1"})
        assert request.headers.get("mcp-session-id") == "sid-1"
        params = body.get("params", {})
        self.calls.append(params)
        name = params.get("name")
        if name == "chrome_navigate":
            assert params["arguments"].get("background") is True
            text = json.dumps({"success": True, "tabId": 42})
        elif name == "chrome_javascript":
            code = params["arguments"]["code"]
            if "link.click()" in code:
                import re as _re
                idx = int(_re.search(r"const li = lis\[(\d+)\]", code).group(1))
                row = LIST_ROWS[idx]
                text = json.dumps({"success": True, "result": json.dumps({"ok": True, "name": row["name"], "hex": _hex(PATHS[idx])})})
            elif "conversations-list" in code:
                text = json.dumps({"success": True, "result": json.dumps({"ok": True, "rows": LIST_ROWS})})
            else:
                text = json.dumps({"success": True, "result": "ok"})
        else:
            raise AssertionError(f"unexpected tool {name}")
        # SSE framing, as the real bridge answers
        payload = {"jsonrpc": "2.0", "id": 7, "result": {"content": [{"type": "text", "text": text}]}}
        return httpx.Response(200, headers={"mcp-session-id": "sid-1", "content-type": "text/event-stream"},
                              content=("event: message\ndata: " + json.dumps(payload) + "\n\n").encode())


def test_inbox_scan_uses_background_and_one_script(tmp_path):
    transport = _FakeBridgeTransport()
    session_file = str(tmp_path / "session-id")
    with httpx.Client(transport=transport) as client:
        inbox = LinkedInInbox(ChromeBridge(client, url="http://bridge.test/mcp", session_file=session_file))
        threads = inbox.read_inbox(now=NOW)
    assert (tmp_path / "session-id").read_text() == "sid-1"
    assert [t.counterparty for t in threads] == ["Ada Quill", "Bram Holt", "Cy Marlow", "LinkedIn", "Dee Voss"]
    assert all(t.thread_url == "" for t in threads)
    with httpx.Client(transport=transport) as client:
        inbox = LinkedInInbox(ChromeBridge(client, url="http://bridge.test/mcp", session_file=session_file), tab_id=42)
        resolved = inbox.resolve_thread_urls([threads[0], threads[2]])
    assert [t.thread_url for t in resolved] == ["https://www.linkedin.com/messaging/thread/2-abc/", "https://www.linkedin.com/messaging/thread/2-ghi/"]
    tools = [c["name"] for c in transport.calls]
    assert "chrome_computer" not in tools
    assert tools.count("chrome_navigate") == 1
    assert sum(1 for c in transport.calls if c["name"] == "chrome_javascript" and "rows.push" in c["arguments"]["code"]) == 1
    assert sum(1 for c in transport.calls if c["name"] == "chrome_javascript" and "link.click()" in c["arguments"]["code"]) == 2
    assert all(c["arguments"].get("tabId") == 42 for c in transport.calls if c["name"] == "chrome_javascript")


def test_bridge_reuses_shared_session_and_reports_second_transport(tmp_path):
    transport = _FakeBridgeTransport()
    session_file = str(tmp_path / "session-id")
    with httpx.Client(transport=transport) as client:
        ChromeBridge(client, url="http://bridge.test/mcp", session_file=session_file).connect()
        # A second client with the shared file pings instead of re-initializing.
        second = ChromeBridge(client, url="http://bridge.test/mcp", session_file=session_file)
        second.connect()
        assert transport.initialized == 1
        # A client with a stale id and no way to share: the bridge's 500 becomes a clear reason.
        stale = ChromeBridge(client, url="http://bridge.test/mcp", session_id="dead", session_file=None)
        try:
            stale.connect()
        except BridgeUnavailable as exc:
            assert "already holds a session" in exc.reason
        else:
            raise AssertionError("expected BridgeUnavailable")
