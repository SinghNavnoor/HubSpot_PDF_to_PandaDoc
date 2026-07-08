from datetime import date

import pytest

from hubspot_field_map import (
    ASSISTANCE_PAYMENT_MONTH_PROPERTY,
    BATCH_SCHEDULED_RUN_DAY,
    FILTER_CREATE_DATE_DAY,
    HUBSPOT_CREATEDATE_PROPERTY,
)
from hubspot_pull import (
    batch_create_date_target,
    batch_search_filters,
    build_document_name,
    create_date_filters_for_batch,
    format_hubspot_createdate,
    properties_to_fetch,
    pull_batch,
    search_matching_deals,
)
from unittest.mock import Mock

from hubspot_pull import get_rows_for_batch, hubspot_deal_to_row

FAKE_FIELD_MAP = {
    "internal_client_name": "Client Name",
    "internal_program": "Program (Sync)",
}


def test_create_date_filters_for_july_2026():
    filters = create_date_filters_for_batch(date(2026, 7, 20))
    assert batch_create_date_target(date(2026, 7, 20)) == date(2026, 7, 13)
    assert len(filters) == 2
    assert filters[0]["propertyName"] == HUBSPOT_CREATEDATE_PROPERTY
    assert filters[0]["operator"] == "GTE"
    assert filters[1]["operator"] == "LT"
    # 2026-07-13 00:00:00 UTC
    assert filters[0]["value"] == "1783900800000"
    assert filters[1]["value"] == "1783987200000"


def test_batch_search_filters_includes_all_three_criteria():
    filters = batch_search_filters(date(2026, 7, 20))
    property_names = [f["propertyName"] for f in filters]
    assert property_names.count("check_type") == 1
    assert property_names.count("paid_status") == 1
    assert property_names.count("type_of_rental_assitance") == 1
    assert property_names.count(HUBSPOT_CREATEDATE_PROPERTY) == 2
    assert len(filters) == 5


def test_batch_search_filters_without_create_date():
    filters = batch_search_filters(date(2026, 7, 20), require_create_date=False)
    assert len(filters) == 3


def test_properties_to_fetch_includes_naming_fields():
    props = properties_to_fetch(FAKE_FIELD_MAP)
    assert ASSISTANCE_PAYMENT_MONTH_PROPERTY in props
    assert HUBSPOT_CREATEDATE_PROPERTY in props
    assert "internal_client_name" in props


def test_format_hubspot_createdate_iso_and_epoch():
    assert format_hubspot_createdate("2026-07-13T18:22:11.123Z") == "2026-07-13"
    assert format_hubspot_createdate("1783900800000") == "2026-07-13"


def test_build_document_name_from_batch():
    deals = [
        {
            ASSISTANCE_PAYMENT_MONTH_PROPERTY: "July",
            HUBSPOT_CREATEDATE_PROPERTY: "2026-07-13T10:00:00.000Z",
        },
        {
            ASSISTANCE_PAYMENT_MONTH_PROPERTY: "July",
            HUBSPOT_CREATEDATE_PROPERTY: "1783900800000",
        },
    ]
    assert build_document_name(deals) == "Check Request - July - 2026-07-13"


def test_build_document_name_rejects_mixed_months():
    deals = [
        {ASSISTANCE_PAYMENT_MONTH_PROPERTY: "July", HUBSPOT_CREATEDATE_PROPERTY: "2026-07-13"},
        {ASSISTANCE_PAYMENT_MONTH_PROPERTY: "August", HUBSPOT_CREATEDATE_PROPERTY: "2026-07-13"},
    ]
    with pytest.raises(ValueError, match="mixed assistance payment months"):
        build_document_name(deals)


def test_search_matching_deals_single_page():
    client = Mock()
    client.post.return_value = {
        "results": [
            {"id": "1", "properties": {"internal_client_name": "Client X"}},
            {"id": "2", "properties": {"internal_client_name": "Client Y"}},
        ],
        "paging": {},
    }

    deals = search_matching_deals(
        client, field_map=FAKE_FIELD_MAP, reference_date=date(2026, 7, 20)
    )

    assert deals == [
        {"internal_client_name": "Client X"},
        {"internal_client_name": "Client Y"},
    ]
    client.post.assert_called_once()
    call_path, call_body = client.post.call_args[0]
    assert call_path == "/crm/v3/objects/deals/search"
    assert call_body["properties"] == properties_to_fetch(FAKE_FIELD_MAP)
    filters = call_body["filterGroups"][0]["filters"]
    assert len(filters) == 5
    assert filters[0]["propertyName"] == "check_type"
    assert filters[0]["value"] == "Monthly Rent"
    assert filters[1]["propertyName"] == "paid_status"
    assert filters[1]["value"] == "Pending Approval"
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


def test_hubspot_deal_to_row_translates_internal_option_values():
    field_map = {"over_fmr": "Over FMR?"}

    assert hubspot_deal_to_row({"over_fmr": "true"}, field_map) == {"Over FMR?": "Yes"}
    assert hubspot_deal_to_row({"over_fmr": "false"}, field_map) == {"Over FMR?": "No"}
    assert hubspot_deal_to_row({"over_fmr": "maybe"}, field_map) == {
        "Over FMR?": "maybe"
    }


def test_pull_batch_returns_rows_and_document_name():
    client = Mock()
    client.post.return_value = {
        "results": [
            {
                "id": "1",
                "properties": {
                    "internal_client_name": "Client X",
                    ASSISTANCE_PAYMENT_MONTH_PROPERTY: "July",
                    HUBSPOT_CREATEDATE_PROPERTY: "2026-07-13T00:00:00.000Z",
                },
            }
        ],
        "paging": {},
    }

    rows, name = pull_batch(client, field_map=FAKE_FIELD_MAP, reference_date=date(2026, 7, 20))

    assert rows == [{"Client Name": "Client X", "Program (Sync)": ""}]
    assert name == "Check Request - July - 2026-07-13"


def test_get_rows_for_batch_combines_search_and_mapping():
    client = Mock()
    client.post.return_value = {
        "results": [
            {
                "id": "1",
                "properties": {
                    "internal_client_name": "Client X",
                    ASSISTANCE_PAYMENT_MONTH_PROPERTY: "July",
                    HUBSPOT_CREATEDATE_PROPERTY: "2026-07-13T00:00:00.000Z",
                },
            }
        ],
        "paging": {},
    }

    rows = get_rows_for_batch(client, field_map=FAKE_FIELD_MAP)

    assert rows == [{"Client Name": "Client X", "Program (Sync)": ""}]


def test_filter_create_date_day_is_13():
    assert FILTER_CREATE_DATE_DAY == 13
    assert BATCH_SCHEDULED_RUN_DAY == 16


def test_batch_create_date_target_uses_reference_month():
    assert batch_create_date_target(date(2026, 10, 20)) == date(2026, 10, 13)
    assert batch_create_date_target(date(2026, 3, 20)) == date(2026, 3, 13)
