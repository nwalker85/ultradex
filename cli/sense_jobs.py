"""CLI runner for Dynamic Job Sourcing Engine (Sense #3).

Usage:
    python -m cli.sense_jobs --mock                       # Run mock sourcing across all 10 boards
    python -m cli.sense_jobs --board anthropic --limit 10 # Source from Anthropic board only
    python -m cli.sense_jobs --live                       # Run live scrapers / ATS APIs
    python -m cli.sense_jobs --min-score 80               # Filter qualified leads only
    python -m cli.sense_jobs --json                       # Output JSON formatted leads
    python -m cli.sense_jobs --dry-run                    # Score and display, no database write
    python -m cli.sense_jobs --ingest                     # Submit qualified leads as sources.ingest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any, Optional, Sequence
import uuid

import httpx

from core.database import Database
from core.jobsearch_sourcing import (
    BOARD_REGISTRY,
    JobBoardAdapter,
    JobBoardId,
    JobPosting,
    JobSearchQuery,
    JobSensingSummary,
    JobSourcingEngine,
    JobSweep,
    ProfileMatchScore,
    RawJobPosting,
    ScoredJobLead,
    compute_profile_match,
)
from core.jobsearch_sources import RedisSweepStash


def _format_table(leads: Sequence[Any]) -> str:
    """Render high-contrast terminal table for discovered leads."""
    headers = ["Board", "Employer", "Title", "Location", "Compensation", "Fit Score", "Status"]
    rows: list[list[str]] = []

    for item in leads:
        if isinstance(item, ScoredJobLead):
            p = item.raw_posting
            score_val = item.match_breakdown.score
            comp_str = p.compensation.display_str if p.compensation else "Unlisted"
            status_str = item.status.upper()
            board_str = p.source_board
            emp_str = p.employer
            title_str = p.title
            loc_str = p.location
        elif isinstance(item, dict):
            p_dict = item.get("raw_posting", {})
            score_val = item.get("score", 0)
            comp_str = f"${p_dict.get('salary_min', '')}-${p_dict.get('salary_max', '')}" if p_dict.get("salary_min") else "Unlisted"
            status_str = item.get("state", "discovered").upper()
            board_str = item.get("source_board", "")
            emp_str = item.get("employer", "")
            title_str = item.get("title", "")
            loc_str = item.get("location", "")
        else:
            continue

        rows.append(
            [
                board_str[:12],
                emp_str[:18],
                title_str[:36],
                loc_str[:16],
                comp_str[:20],
                f"{score_val}%",
                status_str,
            ]
        )

    if not rows:
        return "(No leads matched filter criteria)"

    col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers))) + " |"

    lines = [sep, header_line, sep]
    for row in rows:
        row_line = "| " + " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(headers))) + " |"
        lines.append(row_line)
    lines.append(sep)
    return "\n".join(lines)


async def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sense and score open jobs across LinkedIn and 9 Career Boards"
    )
    parser.add_argument(
        "--live", action="store_true", help="Execute live network fetchers / scrapers"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use deterministic mock providers",
    )
    parser.add_argument(
        "--board",
        type=str,
        default="all",
        choices=[
            "all",
            "linkedin",
            "anthropic",
            "openai",
            "parloa",
            "deepgram",
            "soundhound",
            "liveperson",
            "scale_ai",
            "google",
            "aws",
        ],
        help="Filter to specific career board",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Max postings per board"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="Minimum fit score filter (0-100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Score and display leads, do not persist or submit command",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output full results as JSON"
    )
    parser.add_argument(
        "--output", type=Path, help="Save structured results to file"
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Submit qualified leads to Ultradex sources.ingest command",
    )

    args = parser.parse_args(argv)

    target_boards = None
    if args.board != "all":
        target_boards = [args.board]

    engine = JobSourcingEngine()

    if args.json:
        leads = await engine.source_and_score_leads(
            boards=target_boards, min_score=args.min_score
        )
        json_output = json.dumps(leads, indent=2, default=str)
        print(json_output)
        if args.output:
            args.output.write_text(json_output)
        return 0

    summary = await engine.sense_jobs(
        boards=target_boards,
        live=args.live,
        limit_per_board=args.limit,
        min_score=args.min_score,
    )

    # CLI Output Display
    print("================================================================================")
    print(" Career Command Center — Dynamic Job Sourcing Engine (Sense #3)")
    print("================================================================================")
    print(f" Mode: {'LIVE (Network Scrapers)' if args.live else 'MOCK (Deterministic Test Generator)'}")
    print(f" Boards Queried: {', '.join(summary.boards_queried)}")
    print(f" Discovered Postings: {summary.total_discovered}")
    print(
        f" Results: {summary.qualified_count} Qualified (≥80%), "
        f"{summary.watching_count} Watching (60-79%), "
        f"{summary.unqualified_count} Low Fit, "
        f"{summary.excluded_count} Excluded"
    )
    print(f" Duration: {summary.duration_seconds}s")
    print("--------------------------------------------------------------------------------")
    print(_format_table(summary.leads))
    print("--------------------------------------------------------------------------------")

    if args.output:
        args.output.write_text(summary.model_dump_json(indent=2))
        print(f"Saved results to {args.output}")

    if args.dry_run:
        print("Dry run complete — no sweep stashed or command submitted.")
        return 0

    # Sweep and Stash Declaration
    stash = RedisSweepStash.from_env()
    if stash is not None:
        sweep = JobSweep(stash=stash)
        declaration = sweep.run(
            summary.leads,
            query_summary=f"boards:{args.board}:live={args.live}",
        )
        if declaration:
            print(f"Declared: {declaration.source_ref}")
            print(f"          {declaration.commitment}")
            print(f"          {declaration.redacted_summary}")

            if args.ingest:
                token = os.getenv("ULTRADEX_COMMAND_TOKEN") or os.getenv("ULTRADEX_API_TOKEN")
                base = os.getenv("ULTRADEX_API_BASE", "http://127.0.0.1:8000")
                if token:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            f"{base}/api/v2/job-search/commands/sources.ingest",
                            json={
                                "source_kind": declaration.source_kind,
                                "source_ref": declaration.source_ref,
                                "observed_at": declaration.observed_at,
                            },
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Idempotency-Key": f"sense-jobs-{uuid.uuid4()}",
                            },
                        )
                    print(f"Submitted sources.ingest: HTTP {resp.status_code}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
