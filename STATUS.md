# Implementation Status

Tracks progress on the HubSpot → Bulk Word Doc → PandaDoc pipeline. See
`docs/superpowers/specs/2026-06-30-hubspot-pandadoc-pipeline-design.md` for
the full design.

## Phase 1 — HubSpot Pull
Status: Complete (2026-07-06)

- [x] HubSpot API client (`hubspot_client.py`, 4 tests passing)
- [x] Property discovery script (`hubspot_discover_properties.py`, 3 tests passing)
- [x] Deal search + row mapping + batch orchestration (`hubspot_pull.py`, 6 tests passing)
- [x] HubSpot service key (Bulk Check Requests, `crm.objects.deals.read`)
      added to `.env` as `HUBSPOT_API_KEY`
- [x] Field mapping filled from live discovery (`hubspot_field_map.py`, 7
      tests passing) — notable internal names: `type_of_rental_assitance`
      (HubSpot's own typo), `ubh_amount_calc` (plain `ubh_amount` is
      Historical), `mw`/`y` for Payment Month/Year - Calc; `over_fmr` stores
      true/false, translated to Yes/No via `ENGINE_VALUE_TRANSLATIONS`
- [x] Live smoke test — pulled 126 row(s) matching the batch filter, all 16
      row keys correct, per-field fill rates spot-checked (Check Type 126/126,
      UBH Amount 122/126, etc.)
- [x] End-to-end dry run: `python3 run_batch.py --dry-run` generated the
      126-form combined DOCX in `Output/`

## Phase 2 — Document Generation (signature tag addition)
Status: Complete (2026-07-06)

- [x] Opt-in `include_signature_tag` on `fill_template` — writes the PandaDoc
      field tag `{signature:ProgramDirector____________}` in white text into
      the Director signature cell; default off, zero effect on other callers
- [x] `generate_combined_docx(rows, template_path, output_path,
      include_signature_tag=False)` — builds the combined DOCX from in-memory
      row dicts (e.g. `hubspot_pull.get_rows_for_batch()` output); CLI
      refactored to reuse it (7 tests passing)
- [x] Tag syntax verified against live PandaDoc (design spec open item
      closed — see Phase 3 verification below)

## Phase 3 — PandaDoc Push
Status: Complete and verified live (2026-07-06)

- [x] `pandadoc_push.py` — DOCX upload (field tags parsed), Program Director
      recipient bound to the `ProgramDirector` signature role, processing
      poll, auto-send; loud failures (7 tests passing)
- [x] `run_batch.py` — orchestrator chaining Phase 1 → 2 → 3, with
      `--dry-run` running phases 1+2 only (3 tests passing)
- [x] Live PandaDoc verification (2026-07-06, production key, test doc with
      dummy data sent to the user's own email): **square-bracket tag notation
      from the developer docs is silently ignored** — the curly-brace
      notation `{signature:ProgramDirector____}` from PandaDoc's Help Center
      parses correctly. Verified: 2-page test doc produced 2 signature
      fields, recipient upgraded from CC to signer. Tag constant updated in
      `csv_to_word_forms.py`.

## Remaining before first real run

1. User reviews the dry-run DOCX (`Output/Check_Requests_Combined.docx`,
   126 forms) for field placement/formatting
2. User signs (or deletes) the "TEST v3" PandaDoc document sent to their
   email to confirm the signing experience end-to-end
3. Swap `.env`'s `PROGRAM_DIRECTOR_NAME`/`EMAIL` from the user's test
   identity to the real Program Director
4. First real run: `python3 run_batch.py`
