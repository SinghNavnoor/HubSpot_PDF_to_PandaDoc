#!/usr/bin/env python3
"""
CSV to PDF Check Request Form Generator

Reuses all template-filling logic from csv_to_word_forms.py but outputs
only a PDF.  The Word document is created as an intermediate step and
can optionally be kept with --keep-docx.

Requirements (same as csv_to_word_forms.py):
    pip install python-docx docxcompose docx2pdf
Plus one of:
    - Microsoft Word installed (macOS / Windows)  — used by docx2pdf
    - LibreOffice installed (soffice on PATH, or /Applications on macOS)
"""

import argparse
import csv
import sys
import tempfile
from pathlib import Path

from docx import Document
from docxcompose.composer import Composer

# Import all helpers from the existing Word-based script (not modified)
from csv_to_word_forms import (
    build_column_map,
    convert_docx_to_pdf,
    fill_template,
    get_row_values,
    _detect_csv_encoding,
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate PDF check request forms from CSV data."
    )
    parser.add_argument(
        "--data-dir",
        default="Data",
        help="Folder containing the single CSV file (default: Data)",
    )
    parser.add_argument(
        "--template",
        default="Form Template/Rapid Rehousing Program Check Request Form - Template.docx",
        help="Path to Word template",
    )
    parser.add_argument(
        "--output",
        default="Output",
        help="Output directory for generated PDF",
    )
    parser.add_argument(
        "--keep-docx",
        action="store_true",
        help="Keep the intermediate Word document alongside the PDF",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    data_dir = script_dir / args.data_dir
    template_path = script_dir / args.template
    output_dir = script_dir / args.output

    # --- Validate inputs ------------------------------------------------
    if not data_dir.is_dir():
        print(f"Error: Data folder not found: {data_dir}")
        return 1
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        print("Error: No CSV file found in Data folder.")
        return 1
    if len(csv_files) > 1:
        print("Error: More than one CSV file in Data folder. Keep only one.")
        return 1
    csv_path = csv_files[0]

    if not template_path.exists():
        print(f"Error: Template not found: {template_path}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Read CSV and fill templates ------------------------------------
    with open(csv_path, newline="", encoding=_detect_csv_encoding(csv_path)) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        column_map = build_column_map(headers)

        docs_to_merge = []
        for row in reader:
            values = get_row_values(row, column_map)
            doc = Document(template_path)
            fill_template(doc, values, row, column_map)
            docs_to_merge.append(doc)

    if not docs_to_merge:
        print("No rows in CSV. Nothing to generate.")
        return 0

    # --- Merge into a single Word document ------------------------------
    master = docs_to_merge[0]
    composer = Composer(master)
    for doc in docs_to_merge[1:]:
        composer.append(doc)

    # Decide where to save the intermediate .docx
    if args.keep_docx:
        docx_path = output_dir / "Check_Requests_Combined.docx"
    else:
        # Use a temp file so it can be cleaned up automatically
        tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        tmp.close()
        docx_path = Path(tmp.name)

    composer.save(docx_path)

    if args.keep_docx:
        print(f"Generated Word: {docx_path} ({len(docs_to_merge)} form(s))")

    # --- Convert to PDF -------------------------------------------------
    pdf_path = output_dir / "Check_Requests_Combined.pdf"
    if convert_docx_to_pdf(docx_path, pdf_path):
        print(f"Generated PDF:  {pdf_path} ({len(docs_to_merge)} form(s))")
    else:
        print(
            "\nError: Could not create PDF.\n"
            "Install Microsoft Word and `pip install docx2pdf`,\n"
            "or install LibreOffice (soffice on PATH / /Applications on macOS).",
            file=sys.stderr,
        )
        # If we used a temp file, keep it so the user at least has the docx
        if not args.keep_docx:
            fallback = output_dir / "Check_Requests_Combined.docx"
            docx_path.rename(fallback)
            print(f"Kept intermediate Word file: {fallback}")
        return 1

    # Clean up temp docx if not keeping
    if not args.keep_docx and docx_path.exists():
        docx_path.unlink()

    return 0


if __name__ == "__main__":
    exit(main())
