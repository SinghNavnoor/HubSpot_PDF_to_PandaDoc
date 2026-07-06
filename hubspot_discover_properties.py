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
