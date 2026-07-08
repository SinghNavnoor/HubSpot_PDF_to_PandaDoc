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
- [x] **Batch filter tightened (2026-07-07):** Monthly Rent + Pending Approval
      + Type of Assistance = Rent + (production) create date on the 13th.
      PandaDoc document name: `Check Request - {m_p} - {createdate}`.
      Option C: upload as document and send to director.
- [x] **Signature placement (2026-07-07):** moved from oversized DOCX field
      tags to PandaDoc layout API — signature at X=2, Y=9.9; signing-date at
      X=8, same row. Both required; date uses per-field signing-date autofill
      (`settings.autofilled` via API — no workspace-wide date default needed).
- [x] **Cover page dropped, SHPM review step added (2026-07-07):** the SH
      Program Manager cover page broke pagination (merged doc inherited the
      cover's default 1"/1.25" margins instead of the template's 0.5", and no
      page break followed the cover — forms drifted across pages). Reverted to
      the original layout: forms start on page 1, one per page. The SHPM still
      signs first — she gets the page-1 date field (required, manual entry, no
      autofill) so the batch routes to her for review before the Director.

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

- [x] `pandadoc_push.py` — DOCX upload, two recipients in signing order
      (SHPM first, then Program Director; recipient ids resolved by
      signing_order since PandaDoc drops custom role names on file uploads),
      field placement via layout API (Director signature every page, SHPM
      manual date page 1, Director autofilled date pages 2+), processing
      poll, auto-send; loud failures
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

1. User reviews the dry-run DOCX for field placement/formatting (re-run with
   new filter: `python3 run_batch.py --dry-run`)
2. Swap `.env`'s `PROGRAM_DIRECTOR_NAME`/`EMAIL` to the real Program Director
   if still using test identity
3. First real run: `python3 run_batch.py` (document named e.g.
   `Check Request - July - 2026-07-13`, sent to director)
4. **Next fix:** signature field location and size on each page (tags parse
   but placement/size need tuning in the Word template / tag)
5. **Later:** cloud automation for monthly run on the 20th (not started)
