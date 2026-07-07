"""Pull Financial Assistance (Deals) rows from HubSpot for the monthly batch."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from hubspot_client import HubSpotClient
from hubspot_field_map import (
    ENGINE_VALUE_TRANSLATIONS,
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
        value = deal_properties.get(hubspot_name) or ""
        translations = ENGINE_VALUE_TRANSLATIONS.get(engine_header)
        if translations:
            value = translations.get(value, value)
        row[engine_header] = value
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
