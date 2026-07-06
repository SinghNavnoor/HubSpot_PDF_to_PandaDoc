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
