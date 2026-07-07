"""Pull Financial Assistance (Deals) rows from HubSpot for the monthly batch."""
from __future__ import annotations

import os
import sys
import warnings
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv

from hubspot_client import HubSpotClient
from hubspot_field_map import (
    ASSISTANCE_PAYMENT_MONTH_PROPERTY,
    ENGINE_VALUE_TRANSLATIONS,
    FILTER_CHECK_TYPE_PROPERTY,
    FILTER_CHECK_TYPE_VALUE,
    FILTER_CREATE_DATE_DAY,
    FILTER_PAID_STATUS_PROPERTY,
    FILTER_PAID_STATUS_VALUE,
    HUBSPOT_CREATEDATE_PROPERTY,
    HUBSPOT_TO_ENGINE_HEADER,
)

DEALS_SEARCH_PATH = "/crm/v3/objects/deals/search"
SEARCH_PAGE_LIMIT = 100
DOCUMENT_NAME_PREFIX = "Check Request"


def properties_to_fetch(field_map: dict[str, str] | None = None) -> list[str]:
    """HubSpot property internal names requested on every deal search."""
    field_map = field_map or HUBSPOT_TO_ENGINE_HEADER
    names = set(field_map.keys())
    names.add(ASSISTANCE_PAYMENT_MONTH_PROPERTY)
    names.add(HUBSPOT_CREATEDATE_PROPERTY)
    return sorted(names)


def create_date_filters_for_batch(
    reference_date: date | None = None,
    create_day: int = FILTER_CREATE_DATE_DAY,
) -> list[dict]:
    """
    Return HubSpot search filters for deals created on create_day of
    reference_date's month (default: today → 13th of current month).
    """
    reference_date = reference_date or date.today()
    target = date(reference_date.year, reference_date.month, create_day)
    start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return [
        {
            "propertyName": HUBSPOT_CREATEDATE_PROPERTY,
            "operator": "GTE",
            "value": str(int(start.timestamp() * 1000)),
        },
        {
            "propertyName": HUBSPOT_CREATEDATE_PROPERTY,
            "operator": "LT",
            "value": str(int(end.timestamp() * 1000)),
        },
    ]


def batch_search_filters(reference_date: date | None = None) -> list[dict]:
    """All filters for the monthly batch: rent type, paid status, create date."""
    return [
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
        *create_date_filters_for_batch(reference_date),
    ]


def format_hubspot_createdate(raw: str) -> str:
    """Format HubSpot createdate (ms epoch or ISO) as YYYY-MM-DD for naming."""
    s = (raw or "").strip()
    if not s:
        return ""
    if s.isdigit():
        dt = datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
        return dt.date().isoformat()
    if "T" in s:
        return s.split("T", 1)[0]
    return s[:10]


def build_document_name(
    deal_properties_list: list[dict],
    *,
    prefix: str = DOCUMENT_NAME_PREFIX,
) -> str:
    """
    Build the PandaDoc document name from batch metadata on the pulled deals.

    Format: Check Request - {Month} - {Create Date}
    Month  → m_p (Month the Assistance is being paid for)
    Date   → HubSpot createdate on the deal
    """
    if not deal_properties_list:
        raise ValueError("Cannot build document name from an empty batch")

    months: set[str] = set()
    dates: set[str] = set()
    for props in deal_properties_list:
        month = (props.get(ASSISTANCE_PAYMENT_MONTH_PROPERTY) or "").strip()
        if month:
            months.add(month)
        created = format_hubspot_createdate(props.get(HUBSPOT_CREATEDATE_PROPERTY, ""))
        if created:
            dates.add(created)

    if not months:
        raise ValueError(
            f"No {ASSISTANCE_PAYMENT_MONTH_PROPERTY!r} (assistance payment month) "
            "on any deal in the batch"
        )
    if len(months) > 1:
        raise ValueError(
            f"Batch has mixed assistance payment months: {sorted(months)}. "
            "Cannot pick one document name."
        )
    if not dates:
        raise ValueError("No HubSpot createdate on any deal in the batch")
    if len(dates) > 1:
        warnings.warn(
            f"Batch has multiple HubSpot create dates {sorted(dates)}; "
            f"using {min(dates)} for the document name.",
            UserWarning,
            stacklevel=2,
        )

    month = next(iter(months))
    create_date = min(dates)
    return f"{prefix} - {month} - {create_date}"


def search_matching_deals(
    client: HubSpotClient,
    field_map: dict[str, str] | None = None,
    reference_date: date | None = None,
) -> list[dict]:
    """Return raw HubSpot deal property dicts matching the monthly batch filter."""
    field_map = field_map or HUBSPOT_TO_ENGINE_HEADER
    properties = properties_to_fetch(field_map)
    deals: list[dict] = []
    after: str | None = None

    while True:
        body = {
            "filterGroups": [{"filters": batch_search_filters(reference_date)}],
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
        value = deal_properties.get(hubspot_name) or ""
        translations = ENGINE_VALUE_TRANSLATIONS.get(engine_header)
        if translations:
            value = translations.get(value, value)
        row[engine_header] = value
    return row


def pull_batch(
    client: HubSpotClient,
    field_map: dict[str, str] | None = None,
    reference_date: date | None = None,
) -> tuple[list[dict], str]:
    """Pull deals, map to engine rows, and build the PandaDoc document name."""
    field_map = field_map or HUBSPOT_TO_ENGINE_HEADER
    deals = search_matching_deals(client, field_map, reference_date)
    rows = [hubspot_deal_to_row(deal, field_map) for deal in deals]
    document_name = build_document_name(deals) if deals else ""
    return rows, document_name


def get_rows_for_batch(
    client: HubSpotClient,
    field_map: dict[str, str] | None = None,
    reference_date: date | None = None,
) -> list[dict]:
    """Pull and map all deals matching this batch's filter into engine-ready rows."""
    rows, _ = pull_batch(client, field_map, reference_date)
    return rows


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("HUBSPOT_API_KEY", "")
    client = HubSpotClient(api_key)
    rows, document_name = pull_batch(client)

    print(f"Pulled {len(rows)} row(s) from HubSpot.")
    if rows:
        print(f"Document name: {document_name}")
        print(f"Row keys: {sorted(rows[0].keys())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
