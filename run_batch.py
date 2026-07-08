#!/usr/bin/env python3
"""
Orchestrator for the HubSpot → combined DOCX → PandaDoc pipeline.

Runs the three phases in order:
  1. Pull matching Financial Assistance deals from HubSpot (hubspot_pull)
  2. Fill + merge the Word template into one combined DOCX (csv_to_word_forms)
  3. Upload to PandaDoc, place signature/date fields, send (pandadoc_push)

Monthly production schedule (automated via GitHub Actions on the 16th):
  - Job runs on the 16th of each month
  - Includes deals whose HubSpot createdate is the 13th of that same month
    (July 16 → July 13 deals, October 16 → October 13 deals, etc.)

Usage:
    python3 run_batch.py                         # production batch (create-date filter on)
    python3 run_batch.py --dry-run               # phases 1+2 only; no PandaDoc send
    python3 run_batch.py --test-batch            # skip create-date filter (testing)
    python3 run_batch.py --reference-date 2026-06-20   # replay a specific month
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from csv_to_word_forms import generate_combined_docx
from hubspot_client import HubSpotClient
from hubspot_field_map import BATCH_SCHEDULED_RUN_DAY, FILTER_CREATE_DATE_DAY
from hubspot_pull import batch_create_date_target, pull_batch
from pandadoc_push import push_and_send

SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_TEMPLATE = (
    SCRIPT_DIR
    / "Form Template"
    / "Rapid Rehousing Program Check Request Form - Template.docx"
)
DEFAULT_OUTPUT = SCRIPT_DIR / "Output" / "Check_Requests_Combined.docx"


def run(
    dry_run: bool,
    output_path: Path | str = DEFAULT_OUTPUT,
    template_path: Path | str = DEFAULT_TEMPLATE,
    *,
    test_batch: bool = False,
    reference_date: date | None = None,
) -> int:
    load_dotenv()

    reference_date = reference_date or date.today()
    if not test_batch:
        target = batch_create_date_target(reference_date)
        print(
            f"Batch filter: HubSpot createdate on {target.isoformat()} "
            f"(day {FILTER_CREATE_DATE_DAY} of {target.strftime('%B %Y')}). "
            f"Scheduled production run day: {BATCH_SCHEDULED_RUN_DAY}."
        )

    # Phase 1 — HubSpot pull
    client = HubSpotClient(os.environ.get("HUBSPOT_API_KEY", ""))
    rows, document_name = pull_batch(
        client,
        reference_date=reference_date,
        require_create_date=not test_batch,
        test_batch=test_batch,
    )
    print(f"Phase 1: pulled {len(rows)} row(s) from HubSpot.")
    if not rows:
        print("Zero deals match the batch filter. Nothing to generate; exiting.")
        return 0
    print(f"Phase 1: PandaDoc document name will be {document_name!r}.")

    # Phase 2 — combined DOCX (signature fields added via PandaDoc API in Phase 3)
    out = generate_combined_docx(
        rows, template_path, output_path, include_signature_tag=False
    )
    print(f"Phase 2: generated {out} ({len(rows)} form(s)).")

    if dry_run:
        print("Dry run: skipping PandaDoc. Review the DOCX above by hand.")
        return 0

    total_pages = len(rows)  # one form per deal

    # Phase 3 — PandaDoc upload + send (SHPM first, then Program Director)
    document_id = push_and_send(
        out,
        api_key=os.environ.get("PANDADOC_API_KEY", ""),
        shpm_name=os.environ.get("SENIOR_HOUSING_PROGRAM_MANAGER_NAME", ""),
        shpm_email=os.environ.get("SENIOR_HOUSING_PROGRAM_MANAGER_EMAIL", ""),
        director_name=os.environ.get("PROGRAM_DIRECTOR_NAME", ""),
        director_email=os.environ.get("PROGRAM_DIRECTOR_EMAIL", ""),
        document_name=document_name,
        page_count=total_pages,
    )
    print(f"Phase 3: PandaDoc document {document_id} sent.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the HubSpot → DOCX → PandaDoc batch pipeline."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run phases 1+2 only; save the combined DOCX, skip PandaDoc",
    )
    parser.add_argument(
        "--test-batch",
        action="store_true",
        help="Testing only: skip create-date filter (Monthly Rent + Pending Approval + Rent)",
    )
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help=(
            "Month/year for the create-date filter (default: today). "
            f"Production runs on the {BATCH_SCHEDULED_RUN_DAY}th; deals from the "
            f"{FILTER_CREATE_DATE_DAY}th of that month are included."
        ),
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Combined DOCX output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    return run(
        dry_run=args.dry_run,
        output_path=Path(args.output),
        test_batch=args.test_batch,
        reference_date=args.reference_date,
    )


if __name__ == "__main__":
    sys.exit(main())
