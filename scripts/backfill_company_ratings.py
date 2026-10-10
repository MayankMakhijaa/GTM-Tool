#!/usr/bin/env python3
"""
scripts/backfill_company_ratings.py

Safe, targeted rating backfill for existing company records in users_company_details.
Re-runs public rating research ONLY for records where rating is NULL or empty.

Usage:
    # Dry-run (checks and displays results, but makes NO database writes):
    .venv\\Scripts\\python scripts/backfill_company_ratings.py --dry-run

    # Real execution (updates only the rating column for verified ratings):
    .venv\\Scripts\\python scripts/backfill_company_ratings.py

    # Targeted single-user backfill:
    .venv\\Scripts\\python scripts/backfill_company_ratings.py --user-id 149
"""

import sys
import os
import time
import argparse
import logging

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import or_
from app.database import db_session
from app.models.all_models import UsersCompanyDetails
from app.services.scraping_service import research_public_company_ratings

logger = logging.getLogger("rating_backfill")


def backfill_company_ratings(
    dry_run: bool = False,
    delay: float = 3.0,
    user_id: int = None,
    limit: int = None
) -> dict:
    """
    Backfills public ratings for companies with NULL or empty ratings.
    Returns summary statistics dictionary.
    """
    stats = {
        "total_candidates": 0,
        "updated": 0,
        "skipped_not_found": 0,
        "retry_later": 0,
        "skipped_manual_edit": 0,
        "skipped_no_url": 0,
        "errors": 0
    }

    query = db_session.query(UsersCompanyDetails).filter(
        or_(
            UsersCompanyDetails.rating.is_(None),
            UsersCompanyDetails.rating == ""
        )
    )

    if user_id is not None:
        query = query.filter(UsersCompanyDetails.user_id == user_id)

    query = query.order_by(UsersCompanyDetails.id.asc())

    if limit is not None:
        query = query.limit(limit)

    candidates = query.all()
    stats["total_candidates"] = len(candidates)

    print(f"\n{'='*70}")
    print(f"PUBLIC COMPANY RATING BACKFILL {'(DRY RUN - NO WRITES)' if dry_run else '(LIVE RUN)'}")
    print(f"Found {len(candidates)} candidate record(s) with missing rating.")
    print(f"{'='*70}\n")

    for idx, record in enumerate(candidates, start=1):
        c_name = record.company_name or ""
        c_url = record.website_url or ""
        c_loc = record.location
        uid = record.user_id

        # Manual-edit protection: do not overwrite user-edited ratings
        edited_fields = record.edited_fields or []
        if isinstance(edited_fields, (list, set, tuple)) and "rating" in edited_fields:
            print(f"Processing user_id={uid} | company={c_name or 'Unknown'}")
            print(f"Result: SKIPPED (user manually edited rating)")
            print(f"Action: SKIPPED\n")
            stats["skipped_manual_edit"] += 1
            continue

        if not c_url:
            print(f"Processing user_id={uid} | company={c_name or 'Unknown'}")
            print(f"Result: SKIPPED (missing website_url)")
            print(f"Action: SKIPPED\n")
            stats["skipped_no_url"] += 1
            continue

        # If company_name is missing, fallback to domain name
        if not c_name:
            domain = c_url.split("//")[-1].split("/")[0].replace("www.", "")
            c_name = domain.split(".")[0].capitalize()

        print(f"Processing user_id={uid} | company={c_name}")

        try:
            res_map, telemetry = research_public_company_ratings(
                c_name, c_url, location=c_loc
            )

            rating_item = res_map.get("rating", {})
            val = rating_item.get("value")
            vstatus = rating_item.get("verification_status")

            sources_checked = telemetry.get("sources_checked", [])
            print(f"Sources Checked: {', '.join(sources_checked) if sources_checked else 'None'}")
            print(f"Resolution Status: {telemetry.get('status', 'UNKNOWN')}")

            if vstatus == "SEARCH_UNAVAILABLE" or telemetry.get("status") == "SEARCH_UNAVAILABLE":
                print(f"Result: SEARCH_UNAVAILABLE")
                print(f"Action: RETRY_LATER\n")
                stats["retry_later"] += 1
            elif val and val not in ("Not available", "Search unavailable") and vstatus in ("VERIFIED", "UNVERIFIED"):
                print(f"Result: {val}")
                if dry_run:
                    print(f"Action: WOULD_UPDATE (dry-run)\n")
                else:
                    record.rating = val
                    db_session.commit()
                    print(f"Action: UPDATED\n")
                stats["updated"] += 1
            else:
                print(f"Result: NOT_FOUND")
                print(f"Action: SKIPPED\n")
                stats["skipped_not_found"] += 1

        except Exception as e:
            db_session.rollback()
            print(f"Result: ERROR ({str(e)})")
            print(f"Action: SKIPPED (error)\n")
            stats["errors"] += 1

        # Rate limiting delay between external searches
        if idx < len(candidates) and delay > 0:
            time.sleep(delay)

    print(f"{'='*70}")
    print("BACKFILL SUMMARY:")
    print(f"  Total Candidates Evaluated : {stats['total_candidates']}")
    print(f"  {'Would Update' if dry_run else 'Updated'}             : {stats['updated']}")
    print(f"  Skipped (Not Found)        : {stats['skipped_not_found']}")
    print(f"  Retry Later (Search Unavailable): {stats['retry_later']}")
    print(f"  Skipped (Manual Edit)      : {stats['skipped_manual_edit']}")
    print(f"  Skipped (No URL)           : {stats['skipped_no_url']}")
    print(f"  Errors Encountered         : {stats['errors']}")
    print(f"{'='*70}\n")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill missing company ratings using public business review directories."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate backfill without committing any database updates."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Delay in seconds between company searches to prevent search rate limiting (default: 3.0s)."
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Target a specific user_id only."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of candidate records to process."
    )

    args = parser.parse_args()
    backfill_company_ratings(
        dry_run=args.dry_run,
        delay=args.delay,
        user_id=args.user_id,
        limit=args.limit
    )


if __name__ == "__main__":
    main()
