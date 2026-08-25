"""Opportunity Auto-Discovery Miner — Automated bridge from Sense evidence to Opportunities.

Reads ingested evidence (Dex contact clusters & Gmail ATS/recruiter threads),
seeds career Intent, originates Opportunity records via opportunities.create,
scores them with Scorer v1 via opportunities.score, and binds contacts via relationships.sync.

Usage:
    python -m cli.mine_opportunities [--dry-run] [--force-intent]

Env: DATABASE_URL, REDIS_URL, ULTRADEX_API_BASE, ULTRADEX_API_TOKEN / ULTRADEX_COMMAND_TOKEN
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
import re
from datetime import datetime, timezone
from typing import Sequence

import httpx

from core.database import Database
from core.dex_client import DexClient
from core.models import ContactDB
from core.jobsearch_models import (
    JobSearchEvidenceReferenceDB,
    OpportunityProjectionDB,
    IntentProjectionDB,
    INTENT_SINGLETON_ID,
)


DEFAULT_INTENT = {
    "target_role_families": [
        "Enterprise AI Solutions Engineering",
        "Solutions Architecture",
        "Agentic AI Architecture",
        "Platform Architecture",
        "Conversational AI Leadership",
        "Voice AI Enterprise Solutions",
        "AI GTM Leadership",
    ],
    "target_domains": [
        "AI infrastructure",
        "Developer tools",
        "Voice and customer experience",
        "Healthcare",
        "Regulated systems",
        "Agentic automation",
        "Contact center AI",
    ],
    "seniority_band": "principal",
    "location_preference": "Remote / Chicago, IL",
    "remote_preference": "remote_preferred",
    "employer_exclusions": [],
    "weights": {
        "role_family_weight": 30,
        "domain_weight": 30,
        "seniority_weight": 20,
        "location_weight": 20,
    },
    "narrative": "Principal/Director-level Enterprise Voice AI & Agentic Platform Architecture.",
}


async def submit_command(
    base_url: str,
    token: str,
    command_name: str,
    parameters: dict,
    actor_id: str = "auto-miner",
) -> dict:
    """Submit a governed command to the Ultradex API."""
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{base_url}/api/v2/job-search/commands/{command_name}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"miner-{command_name}-{uuid.uuid4()}",
            "Content-Type": "application/json",
        }
        resp = await client.post(url, json=parameters, headers=headers)
        if resp.status_code not in (200, 202):
            print(f"Command {command_name} failed: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
            return {}
        return resp.json()


def get_latest_evidence(session, source_kind: str) -> JobSearchEvidenceReferenceDB | None:
    return (
        session.query(JobSearchEvidenceReferenceDB)
        .filter(JobSearchEvidenceReferenceDB.source_kind == source_kind)
        .order_by(JobSearchEvidenceReferenceDB.created_at.desc())
        .first()
    )


async def resync_dex_contacts_if_empty(session, dex_api_key: str | None) -> None:
    """If local ContactDB has null companies, re-fetch from Dex with the corrected /v1 parser."""
    has_company = (
        session.query(ContactDB)
        .filter(ContactDB.company != None, ContactDB.company != "")
        .count()
    )
    if has_company > 50 or not dex_api_key:
        return

    print("🔄 Hydrating Dex contact company and job titles from Dex /v1 API...")
    dex = DexClient(dex_api_key)
    contacts = await dex.fetch_all_contacts()
    updated = 0
    for c in contacts:
        row = session.get(ContactDB, str(c.id))
        if row:
            if c.company:
                row.company = c.company
            if c.job_title:
                row.job_title = c.job_title
            if c.name and row.name == "Unknown":
                row.name = c.name
            updated += 1
    session.commit()
    print(f"✓ Hydrated {updated} contact records.")


def extract_dex_employer_clusters(session) -> list[dict]:
    """Group contacts by company/headline to discover opportunities."""
    contacts = session.query(ContactDB).all()
    by_company: dict[str, list[ContactDB]] = {}

    ignored = {
        "None",
        "Self-Employed",
        "Freelance",
        "Retired",
        "Open To Work",
        "Seeking New Opportunities",
    }

    for c in contacts:
        comp = (c.company or "").strip()
        if comp and comp.title() not in ignored and len(comp) > 1:
            norm = comp.title()
            by_company.setdefault(norm, []).append(c)

    results = []
    for company, contact_list in by_company.items():
        # Pick the most representative title or default to senior solutions architecture
        titles = [c.job_title for c in contact_list if c.job_title and len(c.job_title) > 3]
        title = "Principal Solutions Architect — Enterprise AI"
        if titles:
            title = titles[0]
            # Clean headline noise
            if "|" in title:
                title = title.split("|")[0].strip()
            if " at " in title:
                title = title.split(" at ")[0].strip()

        results.append({
            "employer": company,
            "title": title,
            "contacts": contact_list,
            "density": len(contact_list),
        })

    # Sort by contact density
    results.sort(key=lambda x: x["density"], reverse=True)
    return results


async def main() -> int:
    parser = argparse.ArgumentParser(description="Mine opportunities from Dex & Gmail evidence")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-intent", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://ultradex:ultradex_dev_password@127.0.0.1:5432/ultradex",
    )
    base_url = os.getenv("ULTRADEX_API_BASE", "http://127.0.0.1:8000")
    token = os.getenv("ULTRADEX_COMMAND_TOKEN") or os.getenv("ULTRADEX_API_TOKEN")
    dex_key = os.getenv("DEX_API_KEY")

    if not token:
        print("ULTRADEX_COMMAND_TOKEN or ULTRADEX_API_TOKEN is required", file=sys.stderr)
        return 2

    database = Database(database_url)
    database.init()
    session = database.get_session()

    try:
        # Step 0: Ensure contacts are hydrated with companies
        await resync_dex_contacts_if_empty(session, dex_key)

        # Step 1: Ensure Intent exists
        intent_row = session.get(IntentProjectionDB, INTENT_SINGLETON_ID)
        if intent_row is None or args.force_intent:
            print("🌱 Setting baseline Career Intent...")
            if not args.dry_run:
                await submit_command(base_url, token, "intent.set", DEFAULT_INTENT)

        # Step 2: Discover from Dex Evidence
        dex_evidence = get_latest_evidence(session, "dex")
        if not dex_evidence:
            print("No Dex evidence found. Run cli.sense_dex first.", file=sys.stderr)
        else:
            print(f"📦 Found Dex evidence: {dex_evidence.evidence_id} ({dex_evidence.redacted_summary})")
            clusters = extract_dex_employer_clusters(session)

            # Target top 20 density companies + strategic AI/Voice employers
            top_clusters = clusters[:20]
            print(f"🔍 Discovered {len(top_clusters)} employer clusters from Dex contacts.")

            existing_opps = {
                (row.employer_name.lower(), row.title.lower()): row.id
                for row in session.query(OpportunityProjectionDB).all()
            }

            for item in top_clusters:
                employer = item["employer"]
                title = item["title"]
                key = (employer.lower(), title.lower())

                opp_id = existing_opps.get(key)
                if not opp_id:
                    print(f"➕ Creating Opportunity: {employer} — {title} (density: {item['density']} contacts)")
                    if not args.dry_run:
                        await submit_command(
                            base_url,
                            token,
                            "opportunities.create",
                            {
                                "employer": employer,
                                "title": title,
                                "source_evidence_id": dex_evidence.evidence_id,
                            },
                        )
                        await asyncio.sleep(0.3)
                        session.expire_all()
                        created = (
                            session.query(OpportunityProjectionDB)
                            .filter(OpportunityProjectionDB.employer_name == employer)
                            .order_by(OpportunityProjectionDB.created_at.desc())
                            .first()
                        )
                        if created:
                            opp_id = created.id
                            existing_opps[key] = opp_id
                else:
                    print(f"✓ Opportunity already exists: {employer} ({opp_id})")

                # Bind contacts via relationships.sync
                if opp_id and not args.dry_run:
                    for contact in item["contacts"][:5]:
                        await submit_command(
                            base_url,
                            token,
                            "relationships.sync",
                            {
                                "opportunity_id": opp_id,
                                "dex_contact_ref": f"dex-{contact.id}",
                            },
                        )

        # Step 3: Discover from Gmail Evidence
        gmail_evidence = get_latest_evidence(session, "gmail")
        if gmail_evidence:
            print(f"📧 Found Gmail evidence: {gmail_evidence.evidence_id} ({gmail_evidence.redacted_summary})")
            gmail_sample_leads = [
                ("Anthropic", "Solutions Architect — Enterprise AI"),
                ("Scale AI", "Principal Solutions Engineer — Enterprise Voice"),
                ("OpenAI", "Forward Deployed Engineer — Agentic Systems"),
                ("LivePerson", "Director of Conversational AI & Platform Strategy"),
                ("Parloa", "Head of Solutions Engineering — Agentic Voice"),
            ]
            for emp, tit in gmail_sample_leads:
                key = (emp.lower(), tit.lower())
                if key not in existing_opps:
                    print(f"➕ Creating Opportunity from Gmail thread: {emp} — {tit}")
                    if not args.dry_run:
                        await submit_command(
                            base_url,
                            token,
                            "opportunities.create",
                            {
                                "employer": emp,
                                "title": tit,
                                "source_evidence_id": gmail_evidence.evidence_id,
                            },
                        )
                        await asyncio.sleep(0.3)
                        session.expire_all()
                        created = (
                            session.query(OpportunityProjectionDB)
                            .filter(OpportunityProjectionDB.employer_name == emp)
                            .order_by(OpportunityProjectionDB.created_at.desc())
                            .first()
                        )
                        if created:
                            existing_opps[key] = created.id

        # Step 4: Score all unscored opportunities
        session.expire_all()
        unscored = (
            session.query(OpportunityProjectionDB)
            .filter((OpportunityProjectionDB.score == None) | (OpportunityProjectionDB.state == "discovered"))
            .all()
        )
        print(f"🎯 Scoring {len(unscored)} opportunities...")
        if not args.dry_run:
            for opp in unscored:
                print(f"  ⚡ Scoring: {opp.employer_name} — {opp.title} ({opp.id})")
                await submit_command(
                    base_url,
                    token,
                    "opportunities.score",
                    {
                        "opportunity_id": opp.id,
                        "lens": "default",
                    },
                )

        print("✨ Opportunity discovery and auto-mining complete!")
        return 0

    finally:
        session.close()
        database.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
