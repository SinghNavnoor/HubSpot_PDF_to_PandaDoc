# HubSpot Pull (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull "Financial Assistance" (HubSpot Deals) records matching this batch's filter directly from HubSpot's API and return them as plain dict rows, keyed by the exact header strings `csv_to_word_forms.py` already expects — so Phase 2 (document generation) can consume them with zero changes to its existing field-matching logic.

**Architecture:** A thin authenticated HTTP client (`hubspot_client.py`) wraps HubSpot's CRM v3 API. A one-off discovery script (`hubspot_discover_properties.py`) lists Deal property internal names, used once to populate a field-mapping config module (`hubspot_field_map.py`). The pull logic itself (`hubspot_pull.py`) searches Deals with the batch filter, paginates, and maps each result through the field-mapping config into engine-ready row dicts.

**Tech Stack:** Python 3.10, `requests` for HTTP, `python-dotenv` for local secrets, `pytest` + `unittest.mock` for tests. No HubSpot SDK — direct REST calls, since the surface area needed (properties list + one search endpoint) is small.

## Global Constraints

- HubSpot credentials are read from a local `.env` file (gitignored) — never hardcoded, never committed. (Design spec, Phase 1 / Configuration & secrets.)
- Batch filter is exactly: `Check Type == "Monthly Rent"` AND `Paid Status == "Pending Approval"`. (Design spec, Phase 1.)
- Output rows must be dicts keyed by the same header strings `csv_to_word_forms.py`'s `FIELD_MAPPING`, `PAYMENT_MONTH_CALC_HEADER`, `PAYMENT_YEAR_CALC_HEADER`, and `TYPE_OF_RENTAL_ASSISTANCE_KEYS` already recognize — Phase 2 must require zero code changes to consume them. (Design spec, Phase 1.)
- A row with missing/malformed data is skipped with a warning, not fatal — this phase does not raise on missing individual fields. (Design spec, Error handling.)
- No scheduler, no cron, no automatic trigger — this phase is invoked manually. (Design spec, Orchestration + user decision 2026-06-30.)
- This phase does not touch PandaDoc or `csv_to_word_forms.py` — those are out of scope here (Phase 2 and Phase 3 respectively).
- Python 3.10+ (matches the existing project environment).

---

## Before you start: what you need

A HubSpot private-app API key with **read access to Deals** (`crm.objects.deals.read` scope). If you don't have one yet:
1. HubSpot → Settings (gear icon) → Integrations → Private Apps → Create a private app.
2. Name it (e.g. "Financial Assistance Pull"), go to the **Scopes** tab, enable `crm.objects.deals.read` under CRM.
3. Create app → copy the generated access token. This is your `HUBSPOT_API_KEY`.

You'll paste this into `.env` in Task 1.

---

### Task 1: Environment & dependency setup

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `.env.example`
- Create: `STATUS.md`

**Interfaces:**
- Produces: `.env` (gitignored, not committed) with `HUBSPOT_API_KEY`, `PANDADOC_API_KEY`, `PROGRAM_DIRECTOR_NAME`, `PROGRAM_DIRECTOR_EMAIL` — later tasks in this plan read `HUBSPOT_API_KEY` via `os.environ`.

- [ ] **Step 1: Update `requirements.txt`**

Replace the file contents with:

```
python-docx>=1.1.0
docxcompose>=1.4.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

(Streamlit is removed — the web app is gone. `requests` and `python-dotenv` are added for the HubSpot client and local secrets. `pytest` is added since there are no tests in this repo yet.)

- [ ] **Step 2: Install dependencies**

Run: `pip3 install -r requirements.txt`
Expected: all five packages install without error.

- [ ] **Step 3: Update `.gitignore`**

Find this block:

```
# Project-specific
Data/
Output/
.streamlit/secrets.toml
```

Replace it with:

```
# Project-specific
Data/
Output/
.env
```

(`.streamlit/secrets.toml` is stale — that folder no longer exists. `.env` replaces it as the local-secrets file to ignore.)

- [ ] **Step 4: Create `.env.example`**

```
HUBSPOT_API_KEY=
PANDADOC_API_KEY=
PROGRAM_DIRECTOR_NAME=
PROGRAM_DIRECTOR_EMAIL=
```

- [ ] **Step 5: Create your real local `.env`**

Copy `.env.example` to `.env` and fill in `HUBSPOT_API_KEY` with the private-app token from the "Before you start" section above. Leave the PandaDoc/Program Director values blank for now — they're not needed until Phase 3.

Run: `cp .env.example .env`

Then edit `.env` by hand to add the real `HUBSPOT_API_KEY` value. Do not commit this file — verify it's ignored:

Run: `git check-ignore .env`
Expected: prints `.env` (confirms it's ignored)

- [ ] **Step 6: Create `STATUS.md`**

```markdown
# Implementation Status

Tracks progress on the HubSpot → Bulk Word Doc → PandaDoc pipeline. See
`docs/superpowers/specs/2026-06-30-hubspot-pandadoc-pipeline-design.md` for
the full design.

## Phase 1 — HubSpot Pull
Status: In progress

- [ ] HubSpot API client
- [ ] Property discovery script
- [ ] Field mapping (HubSpot property → engine header)
- [ ] Deal search + row mapping + batch orchestration
- [ ] Live smoke test against real HubSpot account

## Phase 2 — Document Generation (signature tag addition)
Status: Not started

## Phase 3 — PandaDoc Push
Status: Not started
```

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore .env.example STATUS.md
git commit -m "chore: set up HubSpot pull environment and dependencies"
```

(`.env` itself is gitignored and won't be included — verify with `git status --short` that only the four files above are staged.)

---

### Task 2: HubSpot API client

**Files:**
- Create: `hubspot_client.py`
- Test: `tests/test_hubspot_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `HubSpotClient(api_key: str)` with methods `.get(path: str, params: dict | None = None) -> dict` and `.post(path: str, json_body: dict) -> dict`, both raising `HubSpotAPIError(status_code: int, body: str)` on a non-2xx response. `HubSpotAPIError` and `HubSpotClient` are both importable from `hubspot_client`. Later tasks import both names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hubspot_client.py`:

```python
from unittest.mock import Mock, patch

import pytest

from hubspot_client import HubSpotAPIError, HubSpotClient


def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        HubSpotClient("")


@patch("hubspot_client.requests.get")
def test_get_success_returns_json(mock_get):
    mock_response = Mock(ok=True)
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    client = HubSpotClient("fake-token")
    result = client.get("/crm/v3/properties/deals")

    assert result == {"results": []}
    called_url = mock_get.call_args[0][0]
    assert called_url == "https://api.hubapi.com/crm/v3/properties/deals"
    called_headers = mock_get.call_args[1]["headers"]
    assert called_headers["Authorization"] == "Bearer fake-token"


@patch("hubspot_client.requests.get")
def test_get_error_raises_hubspot_api_error(mock_get):
    mock_response = Mock(ok=False, status_code=401, text="Unauthorized")
    mock_get.return_value = mock_response

    client = HubSpotClient("fake-token")

    with pytest.raises(HubSpotAPIError) as exc_info:
        client.get("/crm/v3/properties/deals")

    assert exc_info.value.status_code == 401


@patch("hubspot_client.requests.post")
def test_post_success_returns_json(mock_post):
    mock_response = Mock(ok=True)
    mock_response.json.return_value = {"results": [{"id": "1"}]}
    mock_post.return_value = mock_response

    client = HubSpotClient("fake-token")
    result = client.post("/crm/v3/objects/deals/search", {"limit": 100})

    assert result == {"results": [{"id": "1"}]}
    called_json = mock_post.call_args[1]["json"]
    assert called_json == {"limit": 100}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hubspot_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hubspot_client'`

- [ ] **Step 3: Write the implementation**

Create `hubspot_client.py`:

```python
"""Thin authenticated HTTP client for the HubSpot CRM v3 API."""
from __future__ import annotations

import requests

HUBSPOT_API_BASE = "https://api.hubapi.com"


class HubSpotAPIError(Exception):
    """Raised when the HubSpot API returns a non-2xx response."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HubSpot API error {status_code}: {body}")


class HubSpotClient:
    """Minimal authenticated client for HubSpot CRM v3 endpoints."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("HubSpot API key is required")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def get(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(
            f"{HUBSPOT_API_BASE}{path}",
            headers=self._headers,
            params=params,
            timeout=30,
        )
        return self._parse(response)

    def post(self, path: str, json_body: dict) -> dict:
        response = requests.post(
            f"{HUBSPOT_API_BASE}{path}",
            headers=self._headers,
            json=json_body,
            timeout=30,
        )
        return self._parse(response)

    @staticmethod
    def _parse(response: requests.Response) -> dict:
        if not response.ok:
            raise HubSpotAPIError(response.status_code, response.text)
        return response.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_hubspot_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add hubspot_client.py tests/test_hubspot_client.py
git commit -m "feat: add HubSpot API client"
```

---

### Task 3: Property discovery script

**Files:**
- Create: `hubspot_discover_properties.py`
- Test: `tests/test_hubspot_discover_properties.py`

**Interfaces:**
- Consumes: `HubSpotClient` from `hubspot_client` (Task 2).
- Produces: `list_deal_properties(client: HubSpotClient) -> list[dict]` and `format_property_line(prop: dict) -> str`, both importable from `hubspot_discover_properties`. Not consumed by later tasks' code — this is a standalone CLI tool used once by hand in Task 4.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hubspot_discover_properties.py`:

```python
from unittest.mock import Mock

from hubspot_discover_properties import format_property_line, list_deal_properties


def test_list_deal_properties_sorted_by_label():
    client = Mock()
    client.get.return_value = {
        "results": [
            {"name": "b_internal", "label": "B Label"},
            {"name": "a_internal", "label": "A Label"},
        ]
    }

    properties = list_deal_properties(client)

    assert [p["label"] for p in properties] == ["A Label", "B Label"]
    client.get.assert_called_once_with("/crm/v3/properties/deals")


def test_format_property_line_without_options():
    line = format_property_line({"name": "client_name", "label": "Client Name"})
    assert "Client Name" in line
    assert "client_name" in line


def test_format_property_line_with_options():
    line = format_property_line(
        {
            "name": "paid_status",
            "label": "Paid Status",
            "options": [{"label": "Pending Approval", "value": "pending_approval"}],
        }
    )
    assert "Pending Approval" in line
    assert "pending_approval" in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hubspot_discover_properties.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hubspot_discover_properties'`

- [ ] **Step 3: Write the implementation**

Create `hubspot_discover_properties.py`:

```python
#!/usr/bin/env python3
"""
List internal property names and labels for HubSpot's Deals object.

Run this once against a real HubSpot account to find the internal property
names needed for hubspot_field_map.py — e.g. which internal name
corresponds to the "Check Type" or "Paid Status" label shown in HubSpot's UI.

Usage:
    python3 hubspot_discover_properties.py [label_or_name_substring]
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from hubspot_client import HubSpotClient


def list_deal_properties(client: HubSpotClient) -> list[dict]:
    """Return HubSpot's Deals property definitions, sorted by label."""
    data = client.get("/crm/v3/properties/deals")
    results = data.get("results", [])
    return sorted(results, key=lambda p: p.get("label", ""))


def format_property_line(prop: dict) -> str:
    """One printable line: label, internal name, and enum options if any."""
    name = prop.get("name", "")
    label = prop.get("label", "")
    options = prop.get("options") or []
    line = f"{label!r:45} -> name={name!r}"
    if options:
        option_pairs = ", ".join(f"{o['label']!r}={o['value']!r}" for o in options)
        line += f"  options: {option_pairs}"
    return line


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("HUBSPOT_API_KEY", "")
    client = HubSpotClient(api_key)
    properties = list_deal_properties(client)

    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    for prop in properties:
        label = prop.get("label", "").lower()
        name = prop.get("name", "").lower()
        if needle and needle not in label and needle not in name:
            continue
        print(format_property_line(prop))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_hubspot_discover_properties.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add hubspot_discover_properties.py tests/test_hubspot_discover_properties.py
git commit -m "feat: add HubSpot Deals property discovery script"
```

---

### Task 4: Field mapping (live discovery required)

This task is different from the others: the *code structure* is fully specified below, but the exact HubSpot internal property name strings can only come from your real HubSpot account — they're not guessable (custom properties can have internal names unrelated to their display label). You'll run the Task 3 script live and transcribe its output.

**Files:**
- Create: `hubspot_field_map.py`
- Test: `tests/test_hubspot_field_map.py`

**Interfaces:**
- Consumes: `FIELD_MAPPING`, `PAYMENT_MONTH_CALC_HEADER`, `PAYMENT_YEAR_CALC_HEADER`, `TYPE_OF_RENTAL_ASSISTANCE_KEYS`, `build_column_map`, `normalize_column_name` from `csv_to_word_forms` (existing engine — read, not modified).
- Produces: `HUBSPOT_TO_ENGINE_HEADER: dict[str, str]`, `FILTER_CHECK_TYPE_PROPERTY: str`, `FILTER_CHECK_TYPE_VALUE: str`, `FILTER_PAID_STATUS_PROPERTY: str`, `FILTER_PAID_STATUS_VALUE: str` — all importable from `hubspot_field_map`. Task 5 imports all five names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_hubspot_field_map.py`:

```python
from csv_to_word_forms import (
    FIELD_MAPPING,
    PAYMENT_MONTH_CALC_HEADER,
    PAYMENT_YEAR_CALC_HEADER,
    TYPE_OF_RENTAL_ASSISTANCE_KEYS,
    build_column_map,
    normalize_column_name,
)
from hubspot_field_map import (
    FILTER_CHECK_TYPE_PROPERTY,
    FILTER_CHECK_TYPE_VALUE,
    FILTER_PAID_STATUS_PROPERTY,
    FILTER_PAID_STATUS_VALUE,
    HUBSPOT_TO_ENGINE_HEADER,
)


def test_mapping_is_nonempty():
    assert len(HUBSPOT_TO_ENGINE_HEADER) > 0


def test_mapping_keys_and_values_are_nonempty_strings():
    for key, value in HUBSPOT_TO_ENGINE_HEADER.items():
        assert isinstance(key, str) and key
        assert isinstance(value, str) and value


def test_mapping_covers_every_field_mapping_header():
    column_map = build_column_map(list(HUBSPOT_TO_ENGINE_HEADER.values()))
    for csv_header, template_label in FIELD_MAPPING:
        assert normalize_column_name(csv_header) in column_map, (
            f"No HubSpot property mapped to CSV header {csv_header!r} "
            f"(needed for template label {template_label!r})"
        )


def test_mapping_covers_payment_month_and_year():
    column_map = build_column_map(list(HUBSPOT_TO_ENGINE_HEADER.values()))
    assert PAYMENT_MONTH_CALC_HEADER in column_map
    assert PAYMENT_YEAR_CALC_HEADER in column_map


def test_mapping_covers_type_of_rental_assistance():
    column_map = build_column_map(list(HUBSPOT_TO_ENGINE_HEADER.values()))
    assert any(key in column_map for key in TYPE_OF_RENTAL_ASSISTANCE_KEYS)


def test_filter_constants_are_nonempty_strings():
    for value in (
        FILTER_CHECK_TYPE_PROPERTY,
        FILTER_CHECK_TYPE_VALUE,
        FILTER_PAID_STATUS_PROPERTY,
        FILTER_PAID_STATUS_VALUE,
    ):
        assert isinstance(value, str) and value


def test_no_leftover_placeholder_values():
    for key in HUBSPOT_TO_ENGINE_HEADER:
        assert not key.startswith("REPLACE_WITH_"), f"Unfilled placeholder: {key!r}"
    for value in (
        FILTER_CHECK_TYPE_PROPERTY,
        FILTER_CHECK_TYPE_VALUE,
        FILTER_PAID_STATUS_PROPERTY,
        FILTER_PAID_STATUS_VALUE,
    ):
        assert not value.startswith("REPLACE_WITH_"), f"Unfilled placeholder: {value!r}"
```

This test is the safety net: it fails if the mapping is missing any header the engine actually needs, and it specifically catches a real gap already found in this codebase — `csv_to_word_forms.py` looks for a column that normalizes to `"type of rental assitance"` or `"type of rental assistance"`, not `"type of assistance"`. Use `"Type of Rental Assistance"` as the output header for that field in Step 4 below, not `"Type of Assistance"`, even though the latter is what an old sample CSV in `Data/` happened to call it.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_hubspot_field_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hubspot_field_map'`

- [ ] **Step 3: Run the discovery script live**

Run: `python3 hubspot_discover_properties.py`

This prints every Deal property's label, internal name, and (for dropdown/enum properties) its option label→value pairs. Find the internal `name=` for each of the following labels (they may not match exactly — HubSpot labels can drift from what's shown here; use judgement and cross-reference against `Data/Book 24(Sheet1).csv`'s header row if unsure):

| Look for label like... | Needed for |
|---|---|
| Client Name | output field |
| Payment Date (Today's Date) | output field |
| Program (Sync) | output field |
| Check Type | output field **and** filter |
| Type of Assistance | output field (map to `"Type of Rental Assistance"`, not `"Type of Assistance"` — see note above) |
| Has the client been Stepped down? | output field |
| Monthly Rent Amount | output field |
| UBH Amount | output field |
| Client Rent Amount | output field |
| Check Payable to (Sync) | output field |
| Landlord Address Sync | output field |
| Household Size Sync | output field |
| Bedroom Sync | output field |
| Over FMR? | output field |
| Payment Month - Calc | output field |
| Payment Year - Calc | output field |
| Paid Status | filter only (not an output field) |

For the two filter properties (`Check Type`, `Paid Status`), also note the exact `options:` **value** (not label) for `"Monthly Rent"` and `"Pending Approval"` respectively — the discovery script prints these as `'Label'='value'` pairs.

- [ ] **Step 4: Write the implementation using the real discovered names**

Create `hubspot_field_map.py`. Replace every `"REPLACE_WITH_..."` placeholder below with the real internal name or option value found in Step 3 — every one of these must be replaced; none should remain in the committed file:

```python
"""
Maps HubSpot Deal (Financial Assistance) property internal names to the
header strings csv_to_word_forms.py already expects from a CSV row.

Internal names below were found by running hubspot_discover_properties.py
against the real HubSpot account on 2026-06-30. Re-run that script and
update this file if HubSpot properties are ever renamed or recreated.
"""
from __future__ import annotations

HUBSPOT_TO_ENGINE_HEADER: dict[str, str] = {
    "REPLACE_WITH_client_name_internal_name": "Client Name",
    "REPLACE_WITH_payment_date_internal_name": "Payment Date (Today's Date)",
    "REPLACE_WITH_program_internal_name": "Program (Sync)",
    "REPLACE_WITH_check_type_internal_name": "Check Type",
    "REPLACE_WITH_type_of_assistance_internal_name": "Type of Rental Assistance",
    "REPLACE_WITH_stepped_down_internal_name": "Has the client been Stepped down?",
    "REPLACE_WITH_monthly_rent_amount_internal_name": "Monthly Rent Amount",
    "REPLACE_WITH_ubh_amount_internal_name": "UBH Amount",
    "REPLACE_WITH_client_rent_amount_internal_name": "Client Rent Amount",
    "REPLACE_WITH_check_payable_to_internal_name": "Check Payable to (Sync)",
    "REPLACE_WITH_landlord_address_internal_name": "Landlord Address Sync",
    "REPLACE_WITH_household_size_internal_name": "Household Size Sync",
    "REPLACE_WITH_bedroom_internal_name": "Bedroom Sync",
    "REPLACE_WITH_over_fmr_internal_name": "Over FMR?",
    "REPLACE_WITH_payment_month_internal_name": "Payment Month - Calc",
    "REPLACE_WITH_payment_year_internal_name": "Payment Year - Calc",
}

# Same internal name as HUBSPOT_TO_ENGINE_HEADER's "Check Type" entry above.
FILTER_CHECK_TYPE_PROPERTY = "REPLACE_WITH_check_type_internal_name"
FILTER_CHECK_TYPE_VALUE = "REPLACE_WITH_monthly_rent_option_value"

FILTER_PAID_STATUS_PROPERTY = "REPLACE_WITH_paid_status_internal_name"
FILTER_PAID_STATUS_VALUE = "REPLACE_WITH_pending_approval_option_value"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_hubspot_field_map.py -v`
Expected: 7 passed

If `test_mapping_covers_every_field_mapping_header` or either of the two follow-up tests fail, the error message names the exact missing CSV header — go back to the discovery output and find the property you missed.

- [ ] **Step 6: Commit**

```bash
git add hubspot_field_map.py tests/test_hubspot_field_map.py
git commit -m "feat: add HubSpot field mapping from live property discovery"
```

---

### Task 5: Deal search, row mapping, and batch orchestration

**Files:**
- Create: `hubspot_pull.py`
- Test: `tests/test_hubspot_pull.py`

**Interfaces:**
- Consumes: `HubSpotClient` from `hubspot_client` (Task 2); `HUBSPOT_TO_ENGINE_HEADER`, `FILTER_CHECK_TYPE_PROPERTY`, `FILTER_CHECK_TYPE_VALUE`, `FILTER_PAID_STATUS_PROPERTY`, `FILTER_PAID_STATUS_VALUE` from `hubspot_field_map` (Task 4).
- Produces: `search_matching_deals(client, field_map=None) -> list[dict]`, `hubspot_deal_to_row(deal_properties: dict, field_map: dict[str, str]) -> dict`, `get_rows_for_batch(client, field_map=None) -> list[dict]` — all importable from `hubspot_pull`. `get_rows_for_batch`'s return value is what Phase 2 will consume as its list of CSV-shaped rows.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hubspot_pull.py`:

```python
from unittest.mock import Mock

from hubspot_pull import get_rows_for_batch, hubspot_deal_to_row, search_matching_deals

FAKE_FIELD_MAP = {
    "internal_client_name": "Client Name",
    "internal_program": "Program (Sync)",
}


def test_search_matching_deals_single_page():
    client = Mock()
    client.post.return_value = {
        "results": [
            {"id": "1", "properties": {"internal_client_name": "Client X"}},
            {"id": "2", "properties": {"internal_client_name": "Client Y"}},
        ],
        "paging": {},
    }

    deals = search_matching_deals(client, field_map=FAKE_FIELD_MAP)

    assert deals == [
        {"internal_client_name": "Client X"},
        {"internal_client_name": "Client Y"},
    ]
    client.post.assert_called_once()
    call_path, call_body = client.post.call_args[0]
    assert call_path == "/crm/v3/objects/deals/search"
    assert call_body["properties"] == ["internal_client_name", "internal_program"]
    assert "after" not in call_body


def test_search_matching_deals_paginates():
    client = Mock()
    client.post.side_effect = [
        {
            "results": [{"id": "1", "properties": {"internal_client_name": "Client X"}}],
            "paging": {"next": {"after": "CURSOR_1"}},
        },
        {
            "results": [{"id": "2", "properties": {"internal_client_name": "Client Y"}}],
            "paging": {},
        },
    ]

    deals = search_matching_deals(client, field_map=FAKE_FIELD_MAP)

    assert len(deals) == 2
    assert client.post.call_count == 2
    second_call_body = client.post.call_args_list[1][0][1]
    assert second_call_body["after"] == "CURSOR_1"


def test_hubspot_deal_to_row_maps_known_fields():
    deal_properties = {"internal_client_name": "Client X", "internal_program": "Housing"}

    row = hubspot_deal_to_row(deal_properties, FAKE_FIELD_MAP)

    assert row == {"Client Name": "Client X", "Program (Sync)": "Housing"}


def test_hubspot_deal_to_row_defaults_missing_fields_to_empty_string():
    row = hubspot_deal_to_row({}, FAKE_FIELD_MAP)

    assert row == {"Client Name": "", "Program (Sync)": ""}


def test_get_rows_for_batch_combines_search_and_mapping():
    client = Mock()
    client.post.return_value = {
        "results": [{"id": "1", "properties": {"internal_client_name": "Client X"}}],
        "paging": {},
    }

    rows = get_rows_for_batch(client, field_map=FAKE_FIELD_MAP)

    assert rows == [{"Client Name": "Client X", "Program (Sync)": ""}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hubspot_pull.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hubspot_pull'`

- [ ] **Step 3: Write the implementation**

Create `hubspot_pull.py`:

```python
"""Pull Financial Assistance (Deals) rows from HubSpot for the monthly batch."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from hubspot_client import HubSpotClient
from hubspot_field_map import (
    FILTER_CHECK_TYPE_PROPERTY,
    FILTER_CHECK_TYPE_VALUE,
    FILTER_PAID_STATUS_PROPERTY,
    FILTER_PAID_STATUS_VALUE,
    HUBSPOT_TO_ENGINE_HEADER,
)

DEALS_SEARCH_PATH = "/crm/v3/objects/deals/search"
SEARCH_PAGE_LIMIT = 100


def search_matching_deals(
    client: HubSpotClient, field_map: dict[str, str] | None = None
) -> list[dict]:
    """Return raw HubSpot deal property dicts matching the monthly batch filter."""
    field_map = field_map or HUBSPOT_TO_ENGINE_HEADER
    properties = list(field_map.keys())
    deals: list[dict] = []
    after: str | None = None

    while True:
        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": FILTER_CHECK_TYPE_PROPERTY,
                            "operator": "EQ",
                            "value": FILTER_CHECK_TYPE_VALUE,
                        },
                        {
                            "propertyName": FILTER_PAID_STATUS_PROPERTY,
                            "operator": "EQ",
                            "value": FILTER_PAID_STATUS_VALUE,
                        },
                    ]
                }
            ],
            "properties": properties,
            "limit": SEARCH_PAGE_LIMIT,
        }
        if after:
            body["after"] = after

        data = client.post(DEALS_SEARCH_PATH, body)
        for result in data.get("results", []):
            deals.append(result.get("properties", {}))

        next_cursor = data.get("paging", {}).get("next", {}).get("after")
        if not next_cursor:
            break
        after = next_cursor

    return deals


def hubspot_deal_to_row(deal_properties: dict, field_map: dict[str, str]) -> dict:
    """Map one HubSpot deal's raw properties dict to an engine-header-keyed row dict."""
    row: dict[str, str] = {}
    for hubspot_name, engine_header in field_map.items():
        row[engine_header] = deal_properties.get(hubspot_name) or ""
    return row


def get_rows_for_batch(
    client: HubSpotClient, field_map: dict[str, str] | None = None
) -> list[dict]:
    """Pull and map all deals matching this batch's filter into engine-ready rows."""
    field_map = field_map or HUBSPOT_TO_ENGINE_HEADER
    deals = search_matching_deals(client, field_map)
    return [hubspot_deal_to_row(deal, field_map) for deal in deals]


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("HUBSPOT_API_KEY", "")
    client = HubSpotClient(api_key)
    rows = get_rows_for_batch(client)

    print(f"Pulled {len(rows)} row(s) from HubSpot.")
    if rows:
        print(f"Row keys: {sorted(rows[0].keys())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_hubspot_pull.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: all tests across `tests/test_hubspot_client.py`, `tests/test_hubspot_discover_properties.py`, `tests/test_hubspot_field_map.py`, and `tests/test_hubspot_pull.py` pass (19 total).

- [ ] **Step 6: Commit**

```bash
git add hubspot_pull.py tests/test_hubspot_pull.py
git commit -m "feat: add HubSpot deal search and batch row pull"
```

---

### Task 6: Live smoke test against the real HubSpot account

No new files — this task verifies Task 1–5's work against production data and closes out Phase 1.

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Run the pull against the real account**

Run: `python3 hubspot_pull.py`

Expected output: `Pulled N row(s) from HubSpot.` where N is a plausible number of deals currently matching `Check Type == "Monthly Rent"` and `Paid Status == "Pending Approval"` (0 is fine if nothing currently matches — check in HubSpot's UI with the same filter to confirm the count lines up), followed by `Row keys: [...]` listing exactly the 16 header strings from `hubspot_field_map.py`'s `HUBSPOT_TO_ENGINE_HEADER` values.

If the count looks wrong, double check in the HubSpot UI (filter Deals by the same two properties/values) before assuming the code is broken — a mismatch is more likely a wrong internal name or option value in `hubspot_field_map.py` from Task 4.

- [ ] **Step 2: Spot-check one row's values**

If `N > 0`, temporarily add `print(rows[0])` after the existing print statements in `hubspot_pull.py`'s `main()`, run again, and confirm the values look like real HubSpot data (a real client name, a real dollar amount, etc.) rather than blank strings across the board — blank values usually mean an internal name in `hubspot_field_map.py` doesn't actually match what's on the deal. Remove the temporary print line afterward (don't commit it).

- [ ] **Step 3: Update STATUS.md**

Change the Phase 1 section to:

```markdown
## Phase 1 — HubSpot Pull
Status: Complete (2026-06-30)

- [x] HubSpot API client
- [x] Property discovery script
- [x] Field mapping (HubSpot property → engine header)
- [x] Deal search + row mapping + batch orchestration
- [x] Live smoke test against real HubSpot account — pulled N row(s) matching the batch filter
```

Replace `N` with the real count observed in Step 1.

- [ ] **Step 4: Commit**

```bash
git add STATUS.md
git commit -m "docs: mark Phase 1 (HubSpot pull) complete"
```

---

## What's next

Phase 2 (adding the opt-in PandaDoc signature-tag capability to `csv_to_word_forms.py`, and wiring `get_rows_for_batch()`'s output into it to produce the combined DOCX) is a separate plan, written once Phase 1 is verified working end-to-end.
