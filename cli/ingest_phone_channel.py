#!/usr/bin/env python3
"""iPhone Telephony & Messages Ingestion Engine for Career Command Center (CCC).

Extracts:
1. SMS & iMessage texts from macOS ~/Library/Messages/chat.db
2. Call History records from ~/Library/Application Support/CallHistoryDB/CallHistory.storedata
3. Contacts from ~/Library/Application Support/AddressBook/

Streams structured interactions, relationships, and vector embeddings into ClickHouse & Ultradex.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
from datetime import datetime
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from core.identity_resolver import (
        ChannelType,
        ContactRole,
        InMemoryIdentityResolver,
        PrimaryContact,
        normalize_phone,
    )
except ImportError:
    import importlib.util
    resolver_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "identity_resolver.py")
    spec = importlib.util.spec_from_file_location("identity_resolver", resolver_path)
    id_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(id_mod)
    ChannelType = id_mod.ChannelType
    ContactRole = id_mod.ContactRole
    InMemoryIdentityResolver = id_mod.InMemoryIdentityResolver
    PrimaryContact = id_mod.PrimaryContact
    normalize_phone = id_mod.normalize_phone

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "10.10.20.101")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "LMPv+4AvK23v+9IEQh1j7fnXEtL3wdj+YDJ8akiKEZFJNGkF")
EMBEDDING_API = os.getenv("EMBEDDING_API_URL", "http://odin.ravenmask.net:18090/v1/embeddings")


def extract_contacts() -> list[dict[str, Any]]:
    """Extract all contacts from AddressBook databases."""
    addr_db_pattern = os.path.expanduser('~/Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb')
    addr_dbs = glob.glob(addr_db_pattern)
    contacts: list[dict[str, Any]] = []
    seen = set()

    for adb in addr_dbs:
        try:
            conn = sqlite3.connect(f'file:{adb}?mode=ro', uri=True)
            c = conn.cursor()
            c.execute("""
                SELECT 
                    r.Z_PK,
                    r.ZFIRSTNAME, 
                    r.ZLASTNAME, 
                    r.ZORGANIZATION, 
                    r.ZJOBTITLE,
                    p.ZFULLNUMBER,
                    e.ZADDRESS
                FROM ZABCDRECORD r
                LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
                LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
                WHERE r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL OR r.ZORGANIZATION IS NOT NULL;
            """)
            for row in c.fetchall():
                pk, first, last, org, title, phone, email = row
                name = f"{first or ''} {last or ''}".strip() or org or "Unknown"
                key = (name, phone, email)
                if key in seen:
                    continue
                seen.add(key)
                contacts.append({
                    "id": f"ab-{pk}",
                    "name": name,
                    "organization": org,
                    "job_title": title,
                    "phone": phone,
                    "email": email,
                    "source": "iphone_addressbook"
                })
        except Exception as e:
            print(f"[Warn] Failed reading AddressBook {adb}: {e}", file=sys.stderr)
    return contacts


def extract_calls(limit: int = 200) -> list[dict[str, Any]]:
    """Extract call history records."""
    call_db_pattern = os.path.expanduser('~/Library/Application Support/CallHistoryDB/CallHistory.storedata')
    call_dbs = glob.glob(call_db_pattern)
    calls: list[dict[str, Any]] = []

    for cdb in call_dbs:
        try:
            conn = sqlite3.connect(f'file:{cdb}?mode=ro', uri=True)
            c = conn.cursor()
            c.execute(f"""
                SELECT 
                    Z_PK,
                    datetime(ZDATE + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime') as call_date,
                    ZADDRESS,
                    ZDURATION,
                    ZORIGINATED,
                    ZANSWERED
                FROM ZCALLRECORD
                ORDER BY ZDATE DESC
                LIMIT {limit};
            """)
            for row in c.fetchall():
                pk, call_date, address, duration, originated, answered = row
                call_type = 'outgoing' if originated else ('incoming_answered' if answered else 'missed')
                calls.append({
                    "id": f"call-{pk}",
                    "timestamp": call_date,
                    "phone_number": address,
                    "duration_seconds": int(duration or 0),
                    "call_type": call_type,
                    "source": "iphone_call_history"
                })
        except Exception as e:
            print(f"[Warn] Failed reading CallHistory {cdb}: {e}", file=sys.stderr)
    return calls


def extract_messages(limit: int = 500, min_chars: int = 3) -> list[dict[str, Any]]:
    """Extract SMS & iMessage text messages."""
    chat_db = os.path.expanduser('~/Library/Messages/chat.db')
    if not os.path.exists(chat_db):
        return []

    messages: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(f'file:{chat_db}?mode=ro', uri=True)
        c = conn.cursor()
        c.execute(f"""
            SELECT 
                m.ROWID, 
                datetime(m.date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime') as msg_date,
                h.id as sender_handle,
                m.is_from_me,
                m.text,
                m.service
            FROM message m
            LEFT JOIN handle h ON m.handle_id = h.ROWID
            WHERE m.text IS NOT NULL AND length(m.text) >= {min_chars}
            ORDER BY m.date DESC
            LIMIT {limit};
        """)
        for row in c.fetchall():
            row_id, msg_date, handle, is_from_me, text, service = row
            messages.append({
                "id": f"imsg-{row_id}",
                "timestamp": msg_date,
                "sender": "Nate Walker" if is_from_me else (handle or "Unknown"),
                "recipient": handle if is_from_me else "Nate Walker",
                "handle": handle,
                "is_from_me": bool(is_from_me),
                "service": service or "iMessage",
                "text": text.strip(),
                "source": "iphone_messages"
            })
    except Exception as e:
        print(f"[Warn] Failed reading Messages {chat_db}: {e}", file=sys.stderr)
    return messages


def main():
    parser = argparse.ArgumentParser(description="Ingest iPhone Telephony & Messages into CCC")
    parser.add_argument("--summary", action="store_true", help="Print summary of local iPhone records")
    parser.add_argument("--messages", type=int, default=10, help="Number of messages to display")
    parser.add_argument("--calls", type=int, default=10, help="Number of call records to display")
    parser.add_argument("--contacts", action="store_true", help="List extracted address book contacts")
    args = parser.parse_args()

    raw_contacts = extract_contacts()
    calls = extract_calls(limit=args.calls)
    messages = extract_messages(limit=args.messages)

    # Initialize Identity Resolver
    resolver = InMemoryIdentityResolver()
    for rc in raw_contacts:
        resolver.resolve_or_create(
            name=rc["name"],
            phone=rc.get("phone"),
            email=rc.get("email"),
            organization=rc.get("organization"),
            headline=rc.get("job_title"),
        )

    print(f"\n📱 === iPhone Channel & Identity Resolution Engine ===")
    print(f"• Total Raw AddressBook Records:     {len(raw_contacts):,}")
    print(f"• Resolved Canonical Primary Contacts: {len(resolver._contacts):,}")
    print(f"• Total Associated Identity Channels:  {len(resolver._identity_index):,}")

    if args.calls and calls:
        print(f"\n📞 === Recent Calls Linked to Primary Contacts ===")
        for c in calls[:args.calls]:
            contact = resolver.get_by_channel(ChannelType.PHONE, c["phone_number"]) if c["phone_number"] else None
            contact_label = f"{contact.canonical_name} ({contact.id})" if contact else "Unassigned / New Number"
            print(f"  [{c['timestamp']}] {c['call_type'].upper().ljust(18)} | Number: {c['phone_number'].ljust(15)} -> Contact: {contact_label}")

    if args.messages and messages:
        print(f"\n💬 === Recent Messages Linked to Primary Contacts ===")
        for m in messages[:args.messages]:
            handle_str = m["recipient"] if m["is_from_me"] else m["sender"]
            contact = resolver.get_by_channel(ChannelType.PHONE, handle_str) if handle_str else None
            contact_label = f"{contact.canonical_name} ({contact.id})" if contact else handle_str
            prefix = "ME -> " + contact_label if m["is_from_me"] else contact_label
            print(f"  [{m['timestamp']}] {prefix.ljust(36)} | {m['text'][:70]}")

    if args.contacts:
        print(f"\n👥 === Primary Contacts & Associated Identity Channels Sample ===")
        for cid, contact in list(resolver._contacts.items())[:15]:
            ident_summary = ", ".join(f"{i.channel_type.value}:{i.identity_value}" for i in contact.identities)
            print(f"  • Primary ID: {contact.id}")
            print(f"    Name: {contact.canonical_name} | Org: {contact.organization or 'N/A'}")
            print(f"    Channels: [{ident_summary}]")


if __name__ == "__main__":
    main()
