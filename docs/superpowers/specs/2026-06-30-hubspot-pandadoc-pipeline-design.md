# Design: HubSpot → Bulk Word Doc → PandaDoc E-Signature Pipeline

**Date:** 2026-06-30
**Status:** Approved

---

## Summary

A backend pipeline that pulls "Financial Assistance" records (HubSpot's Deals object, relabeled) directly from HubSpot, fills the existing Word check-request template once per record, merges everything into a single combined multi-page Word document, and pushes that document to PandaDoc for one signer (a fixed Program Director) to e-sign — with a real signature field auto-detected on every page. Run manually for now; no scheduler, no UI.

---

## Background / current state

This repo started as a copy of an earlier Streamlit CSV-upload project (`bulk_check_request_ubh`). That version's UI, config, and CLI PDF wrapper have been removed as part of this redesign — see "Removed" below. This project replaces the manual "upload a CSV" step with a direct HubSpot pull, and replaces the "download a DOCX" step with a PandaDoc e-signature send.

**Kept, unchanged:**
- `csv_to_word_forms.py` — the core template-filling engine (field mapping, currency/date formatting, assistance-type branching, table row insertion, comments-paragraph underlining). Reused as-is except for one new opt-in addition (see Phase 2).
- `Form Template/Rapid Rehousing Program Check Request Form - Template.docx` — the Word template.
- `Data/Book 24(Sheet1).csv` — a real export from the "Financial Assistance" object. Not used by the pipeline directly, but kept as a reference for HubSpot's export column labels while building Phase 1's field mapping. Gitignored, never committed.

**Removed** (were specific to the old Streamlit CSV-upload version, not needed here): `app.py`, `.streamlit/`, `packages.txt`, `plan.md`, `csv_to_pdf_forms.py`, the old Streamlit design spec, and stray untracked files (`Untitled`, `sugggest.md`). PDF conversion is not part of this pipeline — PandaDoc receives the Word document directly, which is what allows precise field placement.

---

## Architecture

Three independent scripts, chained by a manual orchestrator:

```
run_batch.py                  # orchestrator — runs the 3 phases in order, or --dry-run for phases 1+2 only
├── hubspot_pull.py           # Phase 1: HubSpot Deals → row data
├── csv_to_word_forms.py      # Phase 2: row data → combined DOCX (existing engine, +1 opt-in addition)
└── pandadoc_push.py          # Phase 3: DOCX → PandaDoc, assign signer, send
```

No scheduler is built in this phase. The "run this around the 25th of each month" cadence is handled by the user running `run_batch.py` by hand once the pipeline is proven correct; automatic triggering is explicitly deferred until after manual runs are validated.

---

## Phase 1 — `hubspot_pull.py`

- Authenticates to HubSpot with a private-app API key, stored in a local `.env` (gitignored).
- Queries the Deals API (the "Financial Assistance" object) via HubSpot's CRM Search endpoint, filtered to `Check Type == "Monthly Rent"` AND `Paid Status == "Pending Approval"`.
- Fetches the full set of properties the engine needs (the same fields the CSV used to carry: Client Name, Payment Date, Program, Check Type, Type of Assistance, UBH Amount, Client Rent Amount, Check Payable to, Landlord Address, Household Size, Bedroom count, Over FMR, Stepdown, Payment Month/Year).
- Maps HubSpot's internal property names to the exact header strings `csv_to_word_forms.py` already expects (`"client name"`, `"ubh amount"`, etc.), so **Phase 2 requires no changes to its field-matching logic** — it just receives dict rows shaped identically to the old CSV rows.
- Internal property names are retrieved from HubSpot's properties-list endpoint during implementation, not hand-guessed.
- Output: a list of plain dict rows, in memory (no CSV file required, though nothing prevents writing one for an audit trail if useful later).

---

## Phase 2 — `csv_to_word_forms.py` (one opt-in addition)

- Everything about template filling stays as-is.
- One new capability: an opt-in parameter (e.g. `include_signature_tag=True` on `fill_template`) that, only when explicitly set, writes a hidden PandaDoc field tag into the "Director:" table cell (the exact blank signature-line cell identified in the current template) instead of leaving it blank.
- Default remains off, so this change has zero effect on any other caller of the engine.
- Output: one combined multi-page DOCX — identical structure to today's output, just with an invisible field tag repeated on every page's Director line.

---

## Phase 3 — `pandadoc_push.py`

- Uploads the combined DOCX via PandaDoc's "create document from file" API with field-tag parsing enabled.
- Defines exactly one recipient — the fixed Program Director (name/email from `.env`) — assigned to a "Program Director" role.
- PandaDoc auto-detects the embedded tag on every page and turns it into a real signature field bound to that role. **The exact tag syntax (bracket vs. brace notation, how the role is referenced) will be confirmed against PandaDoc's live developer docs and tested in the PandaDoc sandbox during implementation** — initial research surfaced conflicting syntax details from different doc pages, so this gets pinned down empirically rather than guessed here.
- Once PandaDoc finishes processing the upload, immediately calls the Send API (auto-send — no manual click required).
- The signed document stays in PandaDoc; nothing is written back to HubSpot.

---

## Orchestration — `run_batch.py`

- Runs Phase 1 → Phase 2 → Phase 3 in sequence.
- `--dry-run` flag: runs Phase 1 + 2 only, saves the combined DOCX locally, makes no PandaDoc API call — lets the field mapping and page layout be checked by hand before any real send.

---

## Configuration & secrets

- `.env` file at repo root (gitignored, loaded via `python-dotenv`): `HUBSPOT_API_KEY`, `PANDADOC_API_KEY`, `PROGRAM_DIRECTOR_NAME`, `PROGRAM_DIRECTOR_EMAIL`.

---

## Error handling

- A pulled row missing/malformed required data: skip that row, log a clear warning, continue with the rest (same tolerant behavior the engine already has for CSV rows).
- Zero deals match the HubSpot filter: log and exit cleanly, no PandaDoc call made.
- PandaDoc upload or send failure: fail loudly — non-zero exit, clear error message — since this is run by hand and watched.
- No duplicate-run protection in this phase (explicitly deferred) — running the script twice in the same window will create a second PandaDoc document. Safe to add later (e.g. flipping a HubSpot deal property after a successful run) if it becomes a real problem.

---

## Testing strategy

- Phase 1 + 2 can be exercised end-to-end via `--dry-run`, producing a real combined DOCX to eyeball without touching PandaDoc.
- Phase 3 is built and tested against PandaDoc's developer sandbox (already available on the user's account) before ever pointing at the live/production PandaDoc account.

---

## Progress tracking

- `STATUS.md` at the repo root, created when implementation starts and kept current phase-by-phase as work lands.

---

## Explicitly out of scope for this phase

- Scheduled/automatic triggering (e.g. cron or GitHub Actions on the 25th) — deferred until the pipeline is proven correct running manually.
- Duplicate-run / idempotency protection.
- Writing signed documents or statuses back into HubSpot.
- PDF conversion or PDF output of any kind.

---

## Open items to verify during implementation

- Exact PandaDoc field-tag syntax for a signature field bound to a named recipient role (confirm via live docs + sandbox test before writing `pandadoc_push.py`).
- HubSpot Deal property internal names for the "Financial Assistance" object's relevant fields (retrieve via the HubSpot properties API once the private app exists).
