"""Backfill jobsearch_organizations from opportunities, leads, and contacts.

Usage:
    python -m cli.backfill_organizations [--dry-run]

Env: DATABASE_URL
"""

from __future__ import annotations

import argparse
import os
import sys

from core.database import Database
from core.jobsearch_organization_backfill import backfill_organizations_from_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create organization rows from existing employer/company strings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing.",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 1

    database = Database(database_url)
    session = database.get_session()
    try:
        result = backfill_organizations_from_pipeline(
            session,
            dry_run=args.dry_run,
        )
    finally:
        session.close()
        database.close()

    mode = "dry-run" if result.dry_run else "applied"
    print(f"organization backfill ({mode})")
    print(f"  distinct employers: {result.employer_names_seen}")
    print(f"  organizations created: {result.organizations_created}")
    print(f"  opportunities linked: {result.opportunities_linked}")
    print(f"  leads linked: {result.leads_linked}")
    print(f"  contacts linked: {result.contacts_linked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
