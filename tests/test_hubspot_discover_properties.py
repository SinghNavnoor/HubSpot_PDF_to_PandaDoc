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
