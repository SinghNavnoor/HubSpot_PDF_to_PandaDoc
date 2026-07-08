import json
from unittest.mock import Mock, patch

import pytest

from csv_to_word_forms import PANDADOC_SENIOR_HOUSING_PM_ROLE, PANDADOC_SIGNATURE_ROLE
from pandadoc_push import (
    DATE_FIELD_SETTINGS,
    PandaDocAPIError,
    PandaDocClient,
    REQUIRED_FIELD_SETTINGS,
    build_batch_signature_fields,
    create_document_from_docx,
    date_field_payload,
    place_signature_fields,
    send_document,
    shpm_cover_signature_field_payload,
    signature_field_payload,
    wait_until_draft,
)


def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        PandaDocClient("")


@patch("pandadoc_push.requests.post")
def test_create_document_uploads_docx_with_two_recipients(mock_post, tmp_path):
    docx = tmp_path / "combined.docx"
    docx.write_bytes(b"fake docx bytes")
    mock_response = Mock(ok=True)
    mock_response.json.return_value = {"id": "DOC123", "status": "document.uploaded"}
    mock_post.return_value = mock_response

    client = PandaDocClient("fake-key")
    document_id = create_document_from_docx(
        client,
        docx,
        document_name="Check Requests",
        shpm_name="Emily Manager",
        shpm_email="emily@example.com",
        director_name="Jane Director",
        director_email="jane@example.com",
    )

    assert document_id == "DOC123"
    payload = json.loads(mock_post.call_args[1]["data"]["data"])
    assert len(payload["recipients"]) == 2
    shpm = payload["recipients"][0]
    assert shpm["email"] == "emily@example.com"
    assert shpm["role"] == PANDADOC_SENIOR_HOUSING_PM_ROLE
    assert shpm["signing_order"] == 1
    director = payload["recipients"][1]
    assert director["email"] == "jane@example.com"
    assert director["role"] == PANDADOC_SIGNATURE_ROLE
    assert director["signing_order"] == 2


@patch("pandadoc_push.requests.post")
def test_create_document_error_raises(mock_post, tmp_path):
    docx = tmp_path / "combined.docx"
    docx.write_bytes(b"fake docx bytes")
    mock_post.return_value = Mock(ok=False, status_code=400, text="Bad request")

    client = PandaDocClient("fake-key")

    with pytest.raises(PandaDocAPIError) as exc_info:
        create_document_from_docx(
            client,
            docx,
            document_name="X",
            shpm_name="Emily Manager",
            shpm_email="emily@example.com",
            director_name="Jane Director",
            director_email="jane@example.com",
        )

    assert exc_info.value.status_code == 400


@patch("pandadoc_push.time.sleep")
@patch("pandadoc_push.requests.get")
def test_wait_until_draft_polls_until_ready(mock_get, mock_sleep):
    responses = []
    for status in ("document.uploaded", "document.uploaded", "document.draft"):
        r = Mock(ok=True)
        r.json.return_value = {"id": "DOC123", "status": status}
        responses.append(r)
    mock_get.side_effect = responses

    client = PandaDocClient("fake-key")
    wait_until_draft(client, "DOC123")

    assert mock_get.call_count == 3


@patch("pandadoc_push.time.sleep")
@patch("pandadoc_push.requests.get")
def test_wait_until_draft_times_out(mock_get, mock_sleep):
    r = Mock(ok=True)
    r.json.return_value = {"id": "DOC123", "status": "document.uploaded"}
    mock_get.return_value = r

    client = PandaDocClient("fake-key")

    with pytest.raises(TimeoutError):
        wait_until_draft(client, "DOC123", timeout_seconds=5, poll_interval_seconds=2)


@patch("pandadoc_push.requests.post")
def test_send_document_posts_to_send_endpoint(mock_post):
    mock_response = Mock(ok=True)
    mock_response.json.return_value = {"id": "DOC123", "status": "document.sent"}
    mock_post.return_value = mock_response

    client = PandaDocClient("fake-key")
    result = send_document(client, "DOC123")

    assert result["status"] == "document.sent"


def test_signature_field_payload_uses_grid_coordinates():
    field = signature_field_payload(3, "recipient-1")
    assert field["type"] == "signature"
    assert field["layout"]["page"] == 3
    assert field["layout"]["position"]["offset_y"] == 841.5
    assert field["settings"] == REQUIRED_FIELD_SETTINGS


def test_shpm_cover_signature_on_page_one():
    field = shpm_cover_signature_field_payload(1, "shpm-1")
    assert field["layout"]["page"] == 1
    assert field["layout"]["position"]["offset_y"] == 467.5
    assert field["assigned_to"] == "shpm-1"


def test_date_field_payload_placed_beside_signature():
    field = date_field_payload(2, "recipient-1")
    assert field["type"] == "date"
    assert field["layout"]["page"] == 2
    assert field["settings"] == DATE_FIELD_SETTINGS


def test_build_batch_signature_fields_cover_plus_two_forms():
    fields = build_batch_signature_fields(
        3, "shpm-1", "dir-1", has_cover_page=True
    )
    assert len(fields) == 5
    assert fields[0]["type"] == "signature"
    assert fields[0]["layout"]["page"] == 1
    assert fields[0]["assigned_to"] == "shpm-1"
    assert fields[1]["layout"]["page"] == 2
    assert fields[2]["layout"]["page"] == 2
    assert fields[3]["layout"]["page"] == 3
    assert fields[4]["layout"]["page"] == 3


@patch("pandadoc_push.requests.post")
@patch("pandadoc_push.get_document_details")
def test_place_signature_fields_skips_cover_for_director(mock_details, mock_post):
    mock_details.return_value = {
        "recipients": [
            {"id": "shpm-1", "role": PANDADOC_SENIOR_HOUSING_PM_ROLE},
            {"id": "dir-1", "role": PANDADOC_SIGNATURE_ROLE},
        ]
    }
    mock_post.return_value = Mock(ok=True, json=Mock(return_value={"fields": []}))

    client = PandaDocClient("fake-key")
    count = place_signature_fields(client, "DOC123", page_count=3)

    assert count == 5
    body = mock_post.call_args[1]["json"]
    pages = [f["layout"]["page"] for f in body["fields"]]
    assert pages == [1, 2, 2, 3, 3]
    assert body["fields"][0]["assigned_to"] == "shpm-1"
    assert body["fields"][1]["assigned_to"] == "dir-1"
