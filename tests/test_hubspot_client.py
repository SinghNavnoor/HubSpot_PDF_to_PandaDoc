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
