# Implementation Status

Tracks progress on the HubSpot → Bulk Word Doc → PandaDoc pipeline. See
`docs/superpowers/specs/2026-06-30-hubspot-pandadoc-pipeline-design.md` for
the full design.

## Phase 1 — HubSpot Pull
Status: Code complete — waiting on user-provided credentials and property names

- [x] HubSpot API client (`hubspot_client.py`, 4 tests passing)
- [x] Property discovery script (`hubspot_discover_properties.py`, 3 tests passing)
- [x] Deal search + row mapping + batch orchestration (`hubspot_pull.py`, 5 tests passing)
- [ ] **PENDING — user to provide HubSpot internal property names** for the
      16 mapped fields plus Paid Status, and the exact option values for the
      two filters (`Check Type == "Monthly Rent"`, `Paid Status ==
      "Pending Approval"`). These go into `hubspot_field_map.py`, replacing
      its `REPLACE_WITH_...` placeholders;
      `tests/test_hubspot_field_map.py::test_no_leftover_placeholder_values`
      passes once done. (Alternative if names are unknown: run
      `python3 hubspot_discover_properties.py` once the API key is in `.env`.)
- [ ] **PENDING — API keys (deferred, user will set up later)**: HubSpot
      private-app token (`crm.objects.deals.read` scope) into `.env` as
      `HUBSPOT_API_KEY`; PandaDoc sandbox/production keys as
      `PANDADOC_API_KEY` (needed for Phase 3, plus `PROGRAM_DIRECTOR_NAME` /
      `PROGRAM_DIRECTOR_EMAIL`).
- [ ] Live smoke test against real HubSpot account (`python3 hubspot_pull.py`)
      — needs both items above

## Phase 2 — Document Generation (signature tag addition)
Status: Complete (2026-07-06)

- [x] Opt-in `include_signature_tag` on `fill_template` — writes the PandaDoc
      field tag `[signature:ProgramDirector____________]` in white text into
      the Director signature cell; default off, zero effect on other callers
- [x] `generate_combined_docx(rows, template_path, output_path,
      include_signature_tag=False)` — builds the combined DOCX from in-memory
      row dicts (e.g. `hubspot_pull.get_rows_for_batch()` output); CLI
      refactored to reuse it (7 tests passing)
- [ ] **PENDING — verify tag syntax in PandaDoc sandbox** (design spec open
      item): confirm `[signature:Role___]` bracket notation renders as a real
      signature field on upload with `parse_form_fields: false`, before
      Phase 3 goes live

## Phase 3 — PandaDoc Push
Status: Code complete (2026-07-06) — untested against live PandaDoc

- [x] `pandadoc_push.py` — DOCX upload (field tags parsed), Program Director
      recipient bound to the `ProgramDirector` signature role, processing
      poll, auto-send; loud failures (7 tests passing)
- [x] `run_batch.py` — orchestrator chaining Phase 1 → 2 → 3, with
      `--dry-run` running phases 1+2 only (3 tests passing)
- [ ] **PENDING — needs API keys**: sandbox test (verify tag → signature
      field on every page, then send) before pointing at production

## Remaining before first real run

1. User provides HubSpot internal property names + filter option values →
   fill `hubspot_field_map.py`
2. User adds `HUBSPOT_API_KEY`, `PANDADOC_API_KEY`,
   `PROGRAM_DIRECTOR_NAME`, `PROGRAM_DIRECTOR_EMAIL` to `.env`
3. Live HubSpot smoke test: `python3 hubspot_pull.py`
4. Dry run + eyeball the DOCX: `python3 run_batch.py --dry-run`
5. PandaDoc sandbox send, verify signature fields, then first real run:
   `python3 run_batch.py`
