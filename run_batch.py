#!/usr/bin/env python3
"""
Manual orchestrator for the HubSpot → combined DOCX → PandaDoc pipeline.

Runs the three phases in order:
  1. Pull matching Financial Assistance deals from HubSpot (hubspot_pull)
  2. Fill + merge the Word template into one combined DOCX, with the PandaDoc
     signature tag on every page's Director line (csv_to_word_forms)
  3. Upload to PandaDoc and auto-send to the Program Director (pandadoc_push)

Usage:
    python3 run_batch.py            # full pipeline
    python3 run_batch.py --dry-run  # phases 1+2 only; saves the DOCX locally,
                                    # makes no PandaDoc API call
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from csv_to_word_forms import generate_combined_docx
from hubspot_client import HubSpotClient
from hubspot_pull import get_rows_for_batch
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
) -> int:
    load_dotenv()

    # Phase 1 — HubSpot pull
    client = HubSpotClient(os.environ.get("HUBSPOT_API_KEY", ""))
    rows = get_rows_for_batch(client)
    print(f"Phase 1: pulled {len(rows)} row(s) from HubSpot.")
    if not rows:
        print("Zero deals match the batch filter. Nothing to generate; exiting.")
        return 0

    # Phase 2 — combined DOCX with signature tags
    out = generate_combined_docx(
        rows, template_path, output_path, include_signature_tag=True
    )
    print(f"Phase 2: generated {out} ({len(rows)} form(s)).")

    if dry_run:
        print("Dry run: skipping PandaDoc. Review the DOCX above by hand.")
        return 0

    # Phase 3 — PandaDoc upload + send
    document_id = push_and_send(
        out,
        api_key=os.environ.get("PANDADOC_API_KEY", ""),
        recipient_name=os.environ.get("PROGRAM_DIRECTOR_NAME", ""),
        recipient_email=os.environ.get("PROGRAM_DIRECTOR_EMAIL", ""),
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
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Combined DOCX output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    return run(dry_run=args.dry_run, output_path=Path(args.output))


if __name__ == "__main__":
    sys.exit(main())
