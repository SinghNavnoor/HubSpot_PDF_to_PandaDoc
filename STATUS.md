# Implementation Status

Tracks progress on the HubSpot → Bulk Word Doc → PandaDoc pipeline. See
`docs/superpowers/specs/2026-06-30-hubspot-pandadoc-pipeline-design.md` for
the full design.

## Phase 1 — HubSpot Pull
Status: Code complete — blocked on HubSpot API key for live discovery + smoke test

- [x] HubSpot API client (`hubspot_client.py`, 4 tests passing)
- [x] Property discovery script (`hubspot_discover_properties.py`, 3 tests passing)
- [x] Deal search + row mapping + batch orchestration (`hubspot_pull.py`, 5 tests passing)
- [ ] **PENDING — HubSpot API key**: create a HubSpot private app with the
      `crm.objects.deals.read` scope and paste its token into `.env` as
      `HUBSPOT_API_KEY`. Required for the two remaining steps below.
- [ ] Field mapping (`hubspot_field_map.py` exists but still has
      `REPLACE_WITH_...` placeholders — run
      `python3 hubspot_discover_properties.py` once the key is in `.env`,
      then fill in the real internal property names and filter option values;
      `tests/test_hubspot_field_map.py::test_no_leftover_placeholder_values`
      passes once done)
- [ ] Live smoke test against real HubSpot account (`python3 hubspot_pull.py`)

## Phase 2 — Document Generation (signature tag addition)
Status: In progress

- [ ] Opt-in `include_signature_tag` on `fill_template` (PandaDoc field tag in
      the Director signature cell)
- [ ] Generate combined DOCX from in-memory rows (no CSV file needed)

## Phase 3 — PandaDoc Push
Status: Not started
