# LinkedIn as an Odin's Runes source (RAV-1906)

The signed-in LinkedIn inbox is scanned through the **mcp-chrome bridge**
(hangwin/mcp-chrome) running inside Nate's own Chrome, and every conversation whose
last message is inbound and unanswered past a grace period becomes a `ccc_linkedin`
task on the hub, in the same shape `cli.owed_replies` posts for email.

## Why a browser bridge and not an API or a headless session

LinkedIn has no messaging API for this account, and it refuses logins and writes from
Playwright's Chromium. The bridge drives the real, signed-in profile, so there is no
session file to refresh and nothing is headless. Verified 2026-09-17: the same session
that 403'd from headless Chromium sent fine from the real browser.

## Rules (learned the first hour)

- **DOM-only, `background: true`, never `chrome_computer`.** The debugger path steals
  macOS focus and is slow; the DOM tools do not touch focus.
- **One in-page script per scan.** `SCAN_SCRIPT` walks the conversation list once and
  returns compact JSON. Threads are opened only for context, one at a time.
- **Strip `= ? & ;` from anything returned.** The bridge refuses output that looks like a
  cookie or a query string.
- **The bridge holds ONE MCP session.** A second `initialize` gets HTTP 500 "Already
  connected to a transport". The client pings a shared session id first
  (`~/var/mcp-chrome/session-id`, or `MCP_CHROME_SESSION_ID`) and only initializes when
  none is alive. Every bridge caller on the laptop must share that file.
- The producer is **laptop-bound**: the bridge exists only where Chrome + the extension
  are connected. The run script exits 0 with a SKIPPED line when port 12306 is not
  listening.

## Selectors (LinkedIn web, 2026-09-17)

| Purpose | Selector |
|---|---|
| Conversation list | `.msg-conversations-container__conversations-list` (rows are `li` with an `a[href*="/messaging/thread/"]`) |
| Row name | `.msg-conversation-listitem__participant-names` (fallback `h3`) |
| Row time label | `time` — `1:17 PM` today, `Sep 14` this year, `Mar 3, 2025` older |
| Row preview | `.msg-conversation-card__message-snippet` — starts with `You:` when Nate wrote last |
| Thread header | `#thread-detail-jump-target` |
| Thread text | `.msg-s-message-list-content` |
| Composer (deliver, phase 2) | `.msg-form__contenteditable`; with "Press Enter to Send" on there is no send button — send is a DOM `keydown/keypress/keyup` Enter |

When LinkedIn changes a class name the scan returns `ok:false` or empty rows; fix the
selector in `core/linkedin_reads.py` and the fixture in `tests/test_linkedin_source.py`.

## Ranking

- Owed when: last message is inbound, older than the grace (24h for a known CCC contact,
  72h for a cold one), and the sender is not LinkedIn itself / sponsored.
- Known contact = display-name match against CCC contacts (`_name_keys`), the same gate the
  email ranker uses for relays. A DM is a person by construction, so unknown senders still
  become tasks, at lower confidence.
- Task id = `ccc-linkedin-` + sha1(thread URL + last inbound time)[:16]: a new inbound
  message after Nate replies is a new task; the same message on the next scan is skipped.
- A thread whose last message is now Nate's closes any open task this producer holds for
  that thread (`PATCH {"status": "completed"}`).

## Running

```
op run --env-file=$HOME/tmp/mail-corpus-admin.env.tpl -- \
  env CCC_CONTACTS_FILE=$HOME/var/ccc/contacts.json ODINSRUNES_API_URL=http://100.106.47.41:8765 \
  .venv311/bin/python -m cli.linkedin_owed_replies --dry-run
```

or `scripts/linkedin-owed-replies-run.sh [--post]`. Scheduling follows the mail pipeline:
n8n owns the cadence and kickstarts a launchd job over SSH; launchd is transport only.

## Hub follow-up

`amp-live-aid` `_channel_and_reply_url` should learn `relay == "linkedin"` → channel
`linkedin` with the thread `reply_url` (today it labels the task `email`). LinkedIn deliver
(assisted, prepare-and-confirm, like Substack in RAV-1886) is phase 2.

## Retired by this source

The uncommitted `zen-linkedin-sensor` Firefox extension and n8n workflow
`CCC: LinkedIn Zen Browser Sensor Stream` (`wzzORR7dcabUEukT`, receives and drops).
