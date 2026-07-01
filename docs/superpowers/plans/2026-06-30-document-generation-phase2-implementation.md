# Document Generation (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Phase 1's pulled HubSpot rows into a single combined multi-page Word document — one filled template page per row — with a hidden PandaDoc signature field tag on every page's Director line, ready for Phase 3 to upload.

**Architecture:** `csv_to_word_forms.py` (the existing engine) gets one opt-in addition: a signature-tag parameter on `fill_template`. A new `document_generation.py` drives the per-row fill + `Composer` merge loop that used to live in `app.py`. A new `run_batch.py` becomes the pipeline's entry point, wiring Phase 1's `get_rows_for_batch()` into `document_generation.py` — with a `--dry-run` flag that stops after saving the DOCX locally (no PandaDoc call, since that's Phase 3).

**Tech Stack:** Same as Phase 1 — Python 3.10, `python-docx`, `docxcompose`, `pytest` + `unittest.mock`.

## Global Constraints

- The signature-tag addition to `fill_template` must be opt-in (default `False`) and change nothing for any caller that doesn't pass it — `fill_template`'s existing behavior for all current callers stays identical. (Design spec, Phase 2.)
- A row that fails while being filled is skipped with a logged warning; it does not abort the batch. (Design spec, Error handling.)
- This phase makes no PandaDoc API calls of any kind — that's Phase 3. `run_batch.py`'s non-`--dry-run` path is a stub in this phase.
- Output is one combined multi-page DOCX, structurally identical to what the old CSV-driven `app.py` produced, plus the invisible tag.
- Python 3.10+, matches Phase 1's environment (already set up: `requirements.txt`, `.env`, `pytest`).

---

### Task 1: Opt-in PandaDoc signature tag in the template engine

**Files:**
- Modify: `csv_to_word_forms.py`
- Test: `tests/test_signature_tag.py`

**Interfaces:**
- Consumes: `collect_all_tables` (existing helper in `csv_to_word_forms.py`, already used by `find_type_of_assistance_table`).
- Produces: `PANDADOC_SIGNATURE_TAG: str` (module constant), `find_director_cell(doc: Document)` returning the table cell or `None`, `apply_signature_tag(doc: Document) -> None`, and `fill_template(doc, values, row, column_map, include_signature_tag: bool = False) -> None` — the new 5th parameter, appended after the existing four so no existing call site needs to change. Task 2 imports `fill_template` and calls it with `include_signature_tag=True`.

The template's Director line was confirmed earlier this project by inspecting the real template file with `collect_all_tables`: it's a table cell whose full text is exactly `"Director:"` (next to a `"Date:"` cell in the same row), and nothing in `FIELD_MAPPING`, `VALUE_IN_NEXT_CELL`, or `UNDERLINE_VALUE_TEMPLATE_LABELS` currently touches it — it's left blank by the existing fill process.

The exact PandaDoc tag string (`[signature:Program Director]`, bracket notation naming the role, per `developers.pandadoc.com/docs/field-tags`) is a best-effort choice based on research done during planning — PandaDoc's docs weren't fully consistent about exact syntax across pages. **Phase 3, Task 4 verifies this against a real PandaDoc sandbox upload and updates the constant here if it turns out wrong.** Don't treat the tag string as immutable while implementing Phase 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_signature_tag.py`:

```python
from pathlib import Path

from docx import Document
from docx.shared import RGBColor

from csv_to_word_forms import (
    PANDADOC_SIGNATURE_TAG,
    build_column_map,
    collect_all_tables,
    fill_template,
    get_row_values,
)

TEMPLATE_PATH = (
    Path(__file__).parent.parent
    / "Form Template"
    / "Rapid Rehousing Program Check Request Form - Template.docx"
)

SAMPLE_ROW = {"Client Name": "Test Client"}


def _director_cell(doc):
    for table in collect_all_tables(doc):
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip().startswith("Director:"):
                    return cell
    return None


def test_fill_template_default_leaves_director_cell_without_tag():
    doc = Document(TEMPLATE_PATH)
    column_map = build_column_map(list(SAMPLE_ROW.keys()))
    values = get_row_values(SAMPLE_ROW, column_map)

    fill_template(doc, values, SAMPLE_ROW, column_map)

    cell = _director_cell(doc)
    assert cell is not None
    assert cell.text.strip() == "Director:"


def test_fill_template_with_signature_tag_adds_tag_to_director_cell():
    doc = Document(TEMPLATE_PATH)
    column_map = build_column_map(list(SAMPLE_ROW.keys()))
    values = get_row_values(SAMPLE_ROW, column_map)

    fill_template(doc, values, SAMPLE_ROW, column_map, include_signature_tag=True)

    cell = _director_cell(doc)
    assert cell is not None
    assert PANDADOC_SIGNATURE_TAG in cell.text

    tag_run = next(
        run
        for paragraph in cell.paragraphs
        for run in paragraph.runs
        if PANDADOC_SIGNATURE_TAG in run.text
    )
    assert tag_run.font.color.rgb == RGBColor(0xFF, 0xFF, 0xFF)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_signature_tag.py -v`
Expected: FAIL — `ImportError: cannot import name 'PANDADOC_SIGNATURE_TAG'`

- [ ] **Step 3: Add the `RGBColor` import**

In `csv_to_word_forms.py`, find:

```python
from docx.shared import Pt
```

Replace with:

```python
from docx.shared import Pt, RGBColor
```

- [ ] **Step 4: Add the signature tag constant**

In `csv_to_word_forms.py`, find the module-level constant block near the top (after `REPLACE_FIRST_ONLY`, `VALUE_IN_NEXT_CELL`, etc. — right before `def normalize_column_name`). Add:

```python
# PandaDoc field-tag syntax for a signature field bound to a named
# recipient role, per developers.pandadoc.com/docs/field-tags. This is
# verified against a real PandaDoc sandbox upload in Phase 3
# (pandadoc_push.py, Task 4) — update this constant there if that
# verification finds a different syntax is required.
PANDADOC_SIGNATURE_TAG = "[signature:Program Director]"
```

- [ ] **Step 5: Add `find_director_cell` and `apply_signature_tag`**

In `csv_to_word_forms.py`, add these two functions directly after `collect_all_tables` (they follow the same "walk all tables including nested" pattern as `find_type_of_assistance_table`):

```python
def find_director_cell(doc: Document):
    """Return the table cell whose text is exactly 'Director:', or None."""
    for table in collect_all_tables(doc):
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip() == "Director:":
                    return cell
    return None


def apply_signature_tag(doc: Document) -> None:
    """
    Append a hidden PandaDoc signature field tag to the Director: cell.

    PandaDoc requires field tag text color to match the page background to
    stay invisible in the rendered document while still being parsed on
    upload, so the tag run's font color is set to white.
    """
    cell = find_director_cell(doc)
    if cell is None:
        warnings.warn(
            "Could not find the 'Director:' cell; skipping signature tag.",
            UserWarning,
            stacklevel=2,
        )
        return
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(f" {PANDADOC_SIGNATURE_TAG}")
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
```

- [ ] **Step 6: Add the opt-in parameter to `fill_template`**

Find the current `fill_template` signature:

```python
def fill_template(
    doc: Document,
    values: dict[str, str],
    row: dict,
    column_map: dict[str, str],
) -> None:
```

Replace with:

```python
def fill_template(
    doc: Document,
    values: dict[str, str],
    row: dict,
    column_map: dict[str, str],
    include_signature_tag: bool = False,
) -> None:
```

Find the end of the function body (after the `Comments:` paragraph loop, the last statement in `fill_template`). Add after it, still inside the function:

```python
    if include_signature_tag:
        apply_signature_tag(doc)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_signature_tag.py -v`
Expected: 2 passed

- [ ] **Step 8: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: all Phase 1 tests still pass, plus the 2 new ones (21 total) — confirms the opt-in default didn't break anything.

- [ ] **Step 9: Commit**

```bash
git add csv_to_word_forms.py tests/test_signature_tag.py
git commit -m "feat: add opt-in PandaDoc signature tag to the Director line"
```

---

### Task 2: Batch document generation

**Files:**
- Create: `document_generation.py`
- Test: `tests/test_document_generation.py`

**Interfaces:**
- Consumes: `build_column_map`, `fill_template`, `get_row_values` from `csv_to_word_forms` (existing engine; Task 1's `include_signature_tag` parameter).
- Produces: `generate_combined_document(rows: list[dict], template_path: Path = TEMPLATE_PATH) -> bytes`, importable from `document_generation`. Task 3 imports and calls this with Phase 1's `get_rows_for_batch()` output.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_document_generation.py`:

```python
import io
from unittest.mock import patch

import pytest
from docx import Document

import document_generation
from document_generation import generate_combined_document


def test_generate_combined_document_merges_all_rows():
    rows = [{"Client Name": "Client A"}, {"Client Name": "Client B"}]

    result = generate_combined_document(rows)

    doc = Document(io.BytesIO(result))
    assert len(doc.tables) == 16  # 8 top-level tables per page x 2 rows


def test_generate_combined_document_raises_on_empty_rows():
    with pytest.raises(ValueError, match="No rows"):
        generate_combined_document([])


def test_generate_combined_document_skips_row_that_raises_and_continues():
    rows = [{"Client Name": "Client A"}, {"Client Name": "Client B"}]
    real_fill_template = document_generation.fill_template

    def flaky_fill_template(doc, values, row, column_map, **kwargs):
        if row["Client Name"] == "Client A":
            raise RuntimeError("simulated failure")
        return real_fill_template(doc, values, row, column_map, **kwargs)

    with patch("document_generation.fill_template", side_effect=flaky_fill_template):
        with pytest.warns(UserWarning, match="Skipping row 0"):
            result = generate_combined_document(rows)

    doc = Document(io.BytesIO(result))
    assert len(doc.tables) == 8  # only Client B's page survived


def test_generate_combined_document_raises_if_all_rows_fail():
    rows = [{"Client Name": "Client A"}]

    with patch("document_generation.fill_template", side_effect=RuntimeError("boom")):
        with pytest.raises(ValueError, match="All rows failed"):
            generate_combined_document(rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_document_generation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'document_generation'`

- [ ] **Step 3: Write the implementation**

Create `document_generation.py`:

```python
"""Build the combined multi-page check-request Word document from HubSpot rows."""
from __future__ import annotations

import io
import warnings
from pathlib import Path

from docx import Document
from docxcompose.composer import Composer

from csv_to_word_forms import build_column_map, fill_template, get_row_values

TEMPLATE_PATH = (
    Path(__file__).parent
    / "Form Template"
    / "Rapid Rehousing Program Check Request Form - Template.docx"
)


def generate_combined_document(
    rows: list[dict], template_path: Path = TEMPLATE_PATH
) -> bytes:
    """
    Fill one template page per row and merge into a single combined DOCX.

    Rows that raise while being filled are skipped with a warning rather
    than aborting the whole batch.
    """
    if not rows:
        raise ValueError("No rows to generate a document from.")

    column_map = build_column_map(list(rows[0].keys()))
    docs = []
    for index, row in enumerate(rows):
        try:
            values = get_row_values(row, column_map)
            doc = Document(template_path)
            fill_template(doc, values, row, column_map, include_signature_tag=True)
            docs.append(doc)
        except Exception as exc:
            warnings.warn(
                f"Skipping row {index} — failed to fill template: {exc}",
                UserWarning,
                stacklevel=2,
            )

    if not docs:
        raise ValueError("All rows failed to generate; no document produced.")

    master = docs[0]
    composer = Composer(master)
    for doc in docs[1:]:
        composer.append(doc)

    buffer = io.BytesIO()
    composer.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_document_generation.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add document_generation.py tests/test_document_generation.py
git commit -m "feat: add batch document generation from HubSpot rows"
```

---

### Task 3: Batch orchestrator with `--dry-run`

**Files:**
- Create: `run_batch.py`
- Test: `tests/test_run_batch.py`

**Interfaces:**
- Consumes: `HubSpotClient` from `hubspot_client`, `get_rows_for_batch` from `hubspot_pull` (both from Phase 1); `generate_combined_document` from `document_generation` (Task 2).
- Produces: `parse_args(argv: list[str] | None = None) -> argparse.Namespace`, `run(dry_run: bool) -> int`, `OUTPUT_DIR: Path` — all importable from `run_batch`. Phase 3 modifies `run()`'s non-dry-run branch and re-uses these same names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_run_batch.py`:

```python
from unittest.mock import patch

from run_batch import parse_args, run


def test_parse_args_defaults_dry_run_false():
    args = parse_args([])
    assert args.dry_run is False


def test_parse_args_dry_run_flag():
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


@patch("run_batch.generate_combined_document")
@patch("run_batch.get_rows_for_batch")
@patch("run_batch.HubSpotClient")
def test_run_dry_run_writes_combined_document(
    mock_client_cls, mock_get_rows, mock_generate, tmp_path, monkeypatch
):
    monkeypatch.setenv("HUBSPOT_API_KEY", "fake-token")
    monkeypatch.setattr("run_batch.OUTPUT_DIR", tmp_path)
    mock_get_rows.return_value = [{"Client Name": "Client A"}]
    mock_generate.return_value = b"fake docx bytes"

    exit_code = run(dry_run=True)

    assert exit_code == 0
    written_files = list(tmp_path.glob("*.docx"))
    assert len(written_files) == 1
    assert written_files[0].read_bytes() == b"fake docx bytes"


@patch("run_batch.generate_combined_document")
@patch("run_batch.get_rows_for_batch")
@patch("run_batch.HubSpotClient")
def test_run_no_rows_skips_generation(
    mock_client_cls, mock_get_rows, mock_generate, monkeypatch
):
    monkeypatch.setenv("HUBSPOT_API_KEY", "fake-token")
    mock_get_rows.return_value = []

    exit_code = run(dry_run=True)

    assert exit_code == 0
    mock_generate.assert_not_called()


@patch("run_batch.generate_combined_document")
@patch("run_batch.get_rows_for_batch")
@patch("run_batch.HubSpotClient")
def test_run_without_dry_run_not_yet_implemented(
    mock_client_cls, mock_get_rows, mock_generate, monkeypatch
):
    monkeypatch.setenv("HUBSPOT_API_KEY", "fake-token")
    mock_get_rows.return_value = [{"Client Name": "Client A"}]
    mock_generate.return_value = b"fake docx bytes"

    exit_code = run(dry_run=False)

    assert exit_code == 1
```

This last test (`test_run_without_dry_run_not_yet_implemented`) will be replaced in Phase 3 once PandaDoc sending is wired in — that's expected and noted in this task, not a gap to fix here.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_run_batch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'run_batch'`

- [ ] **Step 3: Write the implementation**

Create `run_batch.py`:

```python
#!/usr/bin/env python3
"""
Orchestrates the monthly batch: pull from HubSpot, generate the combined
DOCX. --dry-run stops here and saves the DOCX locally; sending the result
to PandaDoc for signature is added in Phase 3.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from document_generation import generate_combined_document
from hubspot_client import HubSpotClient
from hubspot_pull import get_rows_for_batch

OUTPUT_DIR = Path(__file__).parent / "Output"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the monthly check-request batch.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pull from HubSpot and generate the combined DOCX locally; skip PandaDoc entirely.",
    )
    return parser.parse_args(argv)


def run(dry_run: bool) -> int:
    load_dotenv()
    api_key = os.environ.get("HUBSPOT_API_KEY", "")
    client = HubSpotClient(api_key)

    rows = get_rows_for_batch(client)
    print(f"Pulled {len(rows)} row(s) from HubSpot.")
    if not rows:
        print("No rows matched the batch filter. Nothing to generate.")
        return 0

    document_bytes = generate_combined_document(rows)

    if dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / f"Check_Requests_Combined_{date.today().isoformat()}.docx"
        out_path.write_bytes(document_bytes)
        print(f"Dry run: wrote combined document to {out_path}")
        return 0

    print(
        "Non-dry-run mode (sending to PandaDoc) is not implemented yet — "
        "use --dry-run. PandaDoc integration lands in Phase 3."
    )
    return 1


def main() -> int:
    args = parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_run_batch.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: all tests pass (26 total).

- [ ] **Step 6: Commit**

```bash
git add run_batch.py tests/test_run_batch.py
git commit -m "feat: add batch orchestrator with --dry-run"
```

---

### Task 4: Live verification against the real HubSpot account

No new files — this task verifies Tasks 1–3's work end to end and closes out Phase 2.

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Run the dry run against the real account**

Run: `python3 run_batch.py --dry-run`

Expected: `Pulled N row(s) from HubSpot.` (same N as Phase 1's Task 6 smoke test, assuming the same deals still match the filter), followed by `Dry run: wrote combined document to Output/Check_Requests_Combined_<today>.docx`.

- [ ] **Step 2: Open the generated document and inspect it by hand**

Open the file in Word (or any DOCX viewer). Confirm:
- One page per row pulled, each showing the correct client's filled data.
- The "Director:" line looks visually identical to the original template — no visible stray text (the tag is white-on-white, so it should be invisible unless you select the text or change the background).
- Select the text right after "Director:" (click and drag, or Ctrl/Cmd+A) to confirm the hidden tag text `[signature:Program Director]` is actually present, just invisible.

If the tag isn't there or looks wrong, this points back to Task 1's `apply_signature_tag` — don't proceed to Phase 3 until this looks right.

- [ ] **Step 3: Update STATUS.md**

Add a new section:

```markdown
## Phase 2 — Document Generation
Status: Complete (2026-06-30)

- [x] Opt-in PandaDoc signature tag on the Director line
- [x] Batch document generation from HubSpot rows
- [x] Batch orchestrator with --dry-run
- [x] Live verification — dry run produced a correct N-page combined document with hidden signature tags confirmed by hand
```

Replace `N` with the real row count observed in Step 1.

- [ ] **Step 4: Commit**

```bash
git add STATUS.md
git commit -m "docs: mark Phase 2 (document generation) complete"
```

---

## What's next

Phase 3 (uploading the combined document to PandaDoc, verifying the signature tag actually works against a real sandbox, and sending it for signature) is a separate plan, executed once Phase 2 is verified working end-to-end.
