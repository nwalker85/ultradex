"""Read the signed-in LinkedIn inbox through the local mcp-chrome bridge.

The bridge (hangwin/mcp-chrome) runs inside Nate's own Chrome, so the session is
his and the browser is never headless. Everything here is DOM-only and
`background: true`: no `chrome_computer`, nothing that activates the window.
The scan is ONE in-page script over the conversation list; a thread is opened
only when a caller asks for its text.

Bridge protocol: MCP streamable HTTP at `MCP_CHROME_URL` (default
`http://127.0.0.1:12306/mcp`). `initialize` returns an `mcp-session-id` header
that every later call carries; responses come back as JSON or as SSE
`data:` lines. The bridge refuses to return strings that look like cookies or
query strings, so every in-page script strips `= ? & ;` before returning.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import httpx

DEFAULT_BRIDGE_URL = "http://127.0.0.1:12306/mcp"
DEFAULT_SESSION_FILE = "~/var/mcp-chrome/session-id"


def _read_session_file(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as handle:
            value = handle.read().strip()
        return value or None
    except OSError:
        return None


def _write_session_file(path: str | None, sid: str) -> None:
    if not path:
        return
    try:
        full = os.path.expanduser(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(sid)
    except OSError:
        pass
LINKEDIN_MESSAGING_URL = "https://www.linkedin.com/messaging/"
CONVERSATION_LIST = ".msg-conversations-container__conversations-list"
THREAD_HEADER = "#thread-detail-jump-target"
THREAD_TEXT = ".msg-s-message-list-content"

# One walk of the conversation list. Returns compact JSON per row: the
# counterparty's name, the time label LinkedIn renders ("1:17 PM", "Sep 14"),
# whether the preview is ours ("You: …"), and unread state. Rows are Ember
# components with no anchor and no thread id in any attribute (probed
# 2026-09-17), so the thread URL is resolved later, per row, by a DOM click.
# The `clean` step is what keeps the bridge's output filter quiet.
SCAN_SCRIPT = r"""
const clean = s => (s || '').replace(/\s+/g, ' ').replace(/[=?&;]/g, ' ').trim();
const list = document.querySelector('.msg-conversations-container__conversations-list');
if (!list) return JSON.stringify({ok:false, reason:'no conversation list'});
const rows = [];
const lis = [...list.querySelectorAll('li')];
for (let i = 0; i < lis.length; i++) {
  const li = lis[i];
  if (!li.querySelector('.msg-conversation-listitem__link, .msg-conversation-card')) continue;
  const name = clean((li.querySelector('.msg-conversation-listitem__participant-names, h3') || {}).innerText);
  const time = clean((li.querySelector('time') || {}).innerText);
  const snippet = clean((li.querySelector('.msg-conversation-card__message-snippet, p') || {}).innerText);
  const unread = !!li.querySelector('.msg-conversation-card__unread-count') || /unread/.test(li.className);
  if (name) rows.push({i, name, time, snippet, unread});
}
return JSON.stringify({ok:true, rows});
"""

# Click row `i` (DOM click, no focus change) and return the thread pathname.
# The bridge redacts base64-looking strings in script results, and LinkedIn
# thread ids are exactly that, so the path travels as hyphen-joined hex.
RESOLVE_SCRIPT = r"""
const list = document.querySelector('.msg-conversations-container__conversations-list');
if (!list) return JSON.stringify({ok:false, reason:'no conversation list'});
const lis = [...list.querySelectorAll('li')];
const li = lis[__INDEX__];
if (!li) return JSON.stringify({ok:false, reason:'no row'});
const name = ((li.querySelector('.msg-conversation-listitem__participant-names, h3') || {}).innerText || '').replace(/\s+/g, ' ').trim();
const link = li.querySelector('.msg-conversation-listitem__link') || li;
link.click();
await new Promise(r => setTimeout(r, __SETTLE__));
const path = location.pathname;
const hex = Array.from(path).map(c => c.charCodeAt(0).toString(16)).join('-');
return JSON.stringify({ok:true, name, hex});
"""

THREAD_TEXT_SCRIPT = r"""
const clean = s => (s || '').replace(/\s+/g, ' ').replace(/[=?&;]/g, ' ').trim();
const h = document.querySelector('#thread-detail-jump-target');
const t = document.querySelector('.msg-s-message-list-content');
return JSON.stringify({header: clean(h ? h.innerText : ''), text: clean(t ? t.innerText : '').slice(-4000)});
"""

_SYSTEM_NAMES = {"linkedin", "linkedin premium", "linkedin jobs", "linkedin news", "linkedin offer"}
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


class BridgeUnavailable(Exception):
    """The bridge did not answer or refused the call. `reason` is short and
    never carries a body — LinkedIn page text must not end up in an exception."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class LinkedInThread:
    counterparty: str
    thread_url: str
    last_message_text: str
    last_message_from: str  # "me" | "them"
    last_message_at: datetime
    unread: bool = False
    time_label: str = ""
    row_index: int = -1

    def with_url(self, url: str) -> "LinkedInThread":
        return LinkedInThread(self.counterparty, url, self.last_message_text, self.last_message_from,
                              self.last_message_at, self.unread, self.time_label, self.row_index)

    @property
    def is_system(self) -> bool:
        name = self.counterparty.strip().lower()
        return name in _SYSTEM_NAMES or name.startswith("linkedin ") or self.last_message_text.lower().startswith("sponsored")


def parse_time_label(label: str, *, now: datetime) -> datetime:
    """LinkedIn's list shows a clock time for today ("1:17 PM"), a month-day
    for this year ("Sep 14"), and a month-day-year for older ("Mar 3, 2025").
    Best effort: an unparseable label is treated as `now` so a fresh thread is
    never aged into a debt by a formatting change."""
    text = label.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*([AP]M)$", text, re.I)
    if m:
        hour, minute = int(m.group(1)) % 12, int(m.group(2))
        if m.group(3).upper() == "PM":
            hour += 12
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    m = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})(?:,\s*(\d{4}))?$", text)
    if m and m.group(1).lower() in _MONTHS:
        month, day = _MONTHS[m.group(1).lower()], int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        try:
            when = datetime(year, month, day, 12, 0, tzinfo=now.tzinfo)
        except ValueError:
            return now
        if not m.group(3) and when > now + timedelta(days=1):
            when = when.replace(year=year - 1)
        return when
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", text)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = year + 2000 if year < 100 else year
        try:
            return datetime(year, month, day, 12, 0, tzinfo=now.tzinfo)
        except ValueError:
            return now
    return now


def _unhex_path(hexed: str) -> str:
    try:
        return "".join(chr(int(part, 16)) for part in hexed.split("-") if part)
    except ValueError:
        return ""


def rows_to_threads(rows: list[Mapping[str, Any]], *, now: datetime) -> list[LinkedInThread]:
    threads: list[LinkedInThread] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        path = str(row.get("path") or "").strip()
        if not name:
            continue
        snippet = str(row.get("snippet") or "").strip()
        mine = snippet.startswith("You:")
        text = snippet[4:].strip() if mine else snippet
        # An inbound preview may be prefixed with the sender's first name ("Steve: …").
        if not mine and ":" in text[:40]:
            first = text.split(":", 1)[0].strip()
            if first and first.lower() in name.lower():
                text = text.split(":", 1)[1].strip()
        url = ""
        if path:
            url = (path if path.startswith("http") else "https://www.linkedin.com" + path).rstrip("/") + "/"
        threads.append(LinkedInThread(
            counterparty=name, thread_url=url, last_message_text=text,
            last_message_from="me" if mine else "them",
            last_message_at=parse_time_label(str(row.get("time") or ""), now=now),
            unread=bool(row.get("unread")), time_label=str(row.get("time") or ""),
            row_index=int(row.get("i", -1)),
        ))
    return threads


class ChromeBridge:
    """Minimal MCP client for the mcp-chrome bridge: one session, `tools/call`.

    The bridge holds exactly ONE transport at a time: a second `initialize`
    answers HTTP 500 "Already connected to a transport". So the session id is
    shared through a file (`session_file`, default `~/var/mcp-chrome/session-id`,
    overridable by `MCP_CHROME_SESSION_ID`): a known id is tried with `ping`
    first and only a dead one triggers a fresh `initialize`.
    """

    def __init__(self, client: httpx.Client, *, url: str = DEFAULT_BRIDGE_URL, timeout: float = 60.0,
                 session_id: str | None = None, session_file: str | None = DEFAULT_SESSION_FILE) -> None:
        self._client = client
        self._url = url
        self._timeout = timeout
        self._session_file = session_file
        self._sid: str | None = session_id or _read_session_file(session_file)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
        if self._sid:
            headers["mcp-session-id"] = self._sid
        try:
            response = self._client.post(self._url, json=payload, headers=headers, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise BridgeUnavailable(f"bridge unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise BridgeUnavailable(f"bridge HTTP {response.status_code}")
        self._sid = response.headers.get("mcp-session-id") or self._sid
        raw = response.text
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        events = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith("data:")]
        return events[-1] if events else {}

    def connect(self) -> None:
        if self._sid:
            try:
                res = self._post({"jsonrpc": "2.0", "id": 0, "method": "ping"})
                if "error" not in res:
                    self._connected = True
                    return
            except BridgeUnavailable:
                pass
            self._sid = None
        try:
            res = self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "ultradex-linkedin-source", "version": "0"}}})
        except BridgeUnavailable as exc:
            if "500" in exc.reason:
                raise BridgeUnavailable("bridge already holds a session; set MCP_CHROME_SESSION_ID or share the session file") from exc
            raise
        if "error" in res or not self._sid:
            raise BridgeUnavailable("bridge initialize refused")
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except BridgeUnavailable:
            pass
        _write_session_file(self._session_file, self._sid)
        self._connected = True

    def call(self, tool: str, arguments: dict[str, Any]) -> str:
        if not getattr(self, "_connected", False):
            self.connect()
        res = self._post({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                          "params": {"name": tool, "arguments": arguments}})
        if "error" in res:
            raise BridgeUnavailable(f"tool {tool} refused")
        result = res.get("result") or {}
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        if result.get("isError"):
            hint = re.sub(r"[^A-Za-z0-9 :._()-]", " ", " ".join(texts))[:160].strip()
            raise BridgeUnavailable(f"tool {tool} errored: {hint or 'no detail'}")
        return "\n".join(texts)

    def javascript(self, code: str, *, tab_id: int | None = None) -> Any:
        args: dict[str, Any] = {"code": code, "timeoutMs": 30000}
        if tab_id is not None:
            args["tabId"] = tab_id
        text = self.call("chrome_javascript", args)
        try:
            outer = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BridgeUnavailable("javascript result not JSON") from exc
        if isinstance(outer, dict) and outer.get("redacted"):
            raise BridgeUnavailable("javascript result redacted by the bridge")
        inner = outer.get("result") if isinstance(outer, dict) else outer
        if isinstance(inner, str):
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                return inner
        return inner


class LinkedInInbox:
    """The read side. `read_inbox` is the scan; `thread_text` opens one thread."""

    def __init__(self, bridge: ChromeBridge, *, tab_id: int | None = None) -> None:
        self._bridge = bridge
        self._tab_id = tab_id

    def _ensure_messaging_tab(self) -> None:
        args: dict[str, Any] = {"url": LINKEDIN_MESSAGING_URL, "background": True}
        if self._tab_id is not None:
            args["tabId"] = self._tab_id
        text = self._bridge.call("chrome_navigate", args)
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get("tabId"):
                self._tab_id = int(data["tabId"])
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    def read_inbox(self, *, now: datetime | None = None, settle_ms: int = 3500, attempts: int = 4) -> list[LinkedInThread]:
        """Navigate the tab to Messaging (background), wait for the page to
        settle on the CLIENT side (a script sent while the tab is still
        navigating fails with CDP "Inspected target navigated or closed"),
        then scan; retry the scan a few times while the list renders."""
        now = now or datetime.now(timezone.utc)
        self._ensure_messaging_tab()
        time.sleep(settle_ms / 1000.0)
        last_reason = "scan: no result"
        for attempt in range(attempts):
            try:
                data = self._bridge.javascript(SCAN_SCRIPT, tab_id=self._tab_id)
            except BridgeUnavailable as exc:
                last_reason = exc.reason
                data = None
            if isinstance(data, dict) and data.get("ok") and data.get("rows"):
                return rows_to_threads(list(data["rows"]), now=now)
            if isinstance(data, dict) and not data.get("ok"):
                last_reason = "scan: " + str(data.get("reason") or "not ok")
            if attempt + 1 < attempts:
                time.sleep(2.0)
        raise BridgeUnavailable(last_reason)

    def resolve_thread_urls(self, threads: list[LinkedInThread], *, settle_ms: int = 1500) -> list[LinkedInThread]:
        """Click each row (DOM click on the row's link; no focus change) and read the
        thread URL from `location`. Bounded to the threads given — call it for the
        owed candidates, not the whole list. A row whose name no longer matches
        (the list re-sorted underneath us) keeps an empty URL."""
        out: list[LinkedInThread] = []
        for thread in threads:
            if thread.thread_url or thread.row_index < 0:
                out.append(thread)
                continue
            script = RESOLVE_SCRIPT.replace("__INDEX__", str(thread.row_index)).replace("__SETTLE__", str(int(settle_ms)))
            data = self._bridge.javascript(script, tab_id=self._tab_id)
            url = ""
            if isinstance(data, dict) and data.get("ok") and str(data.get("name") or "").strip() == thread.counterparty:
                path = _unhex_path(str(data.get("hex") or ""))
                if "/messaging/thread/" in path:
                    url = "https://www.linkedin.com" + path.rstrip("/") + "/"
            out.append(thread.with_url(url))
        return out

    def thread_text(self, thread: LinkedInThread, *, settle_ms: int = 2500) -> tuple[str, str]:
        """(header, last ~4000 chars of the thread) for context. Opens the thread
        in the background tab; never types."""
        args: dict[str, Any] = {"url": thread.thread_url, "background": True}
        if self._tab_id is not None:
            args["tabId"] = self._tab_id
        self._bridge.call("chrome_navigate", args)
        self._bridge.javascript(f"await new Promise(r => setTimeout(r, {int(settle_ms)})); return 'ok';", tab_id=self._tab_id)
        data = self._bridge.javascript(THREAD_TEXT_SCRIPT, tab_id=self._tab_id)
        if not isinstance(data, dict):
            return "", ""
        return str(data.get("header") or ""), str(data.get("text") or "")
