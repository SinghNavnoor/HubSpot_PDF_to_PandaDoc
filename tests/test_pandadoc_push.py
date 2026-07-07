import json
from unittest.mock import Mock, patch

import pytest

from csv_to_word_forms import PANDADOC_SIGNATURE_ROLE
from pandadoc_push import (
    PandaDocAPIError,
    PandaDocClient,
    create_document_from_docx,
    send_document,
    wait_until_draft,
)


def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        PandaDocClient("")


@patch("pandadoc_push.requests.post")
def test_create_document_uploads_docx_with_recipient_role(mock_post, tmp_path):
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
        recipient_name="Jane Director",
        recipient_email="jane@example.com",
    )

    assert document_id == "DOC123"
    called_url = mock_post.call_args[0][0]
    assert called_url == "https://api.pandadoc.com/public/v1/documents"
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "API-Key fake-key"

    payload = json.loads(mock_post.call_args[1]["data"]["data"])
    assert payload["name"] == "Check Requests"
    assert payload["parse_form_fields"] is False
    recipient = payload["recipients"][0]
    assert recipient["email"] == "jane@example.com"
    assert recipient["first_name"] == "Jane"
    assert recipient["last_name"] == "Director"
    assert recipient["role"] == PANDADOC_SIGNATURE_ROLE

    files = mock_post.call_args[1]["files"]
    assert "file" in files


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
            recipient_name="Jane Director",
            recipient_email="jane@example.com",
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
    called_url = mock_get.call_args[0][0]
    assert called_url == "https://api.pandadoc.com/public/v1/documents/DOC123"


@patch("pandadoc_push.time.sleep")
@patch("pandadoc_push.requests.get")
def test_wait_until_draft_times_out(mock_get, mock_sleep):
    r = Mock(ok=True)
    r.json.return_value = {"id": "DOC123", "status": "document.uploaded"}
    mock_get.return_value = r

    client = PandaDocClient("fake-key")

    with pytest.raises(TimeoutError):
        wait_until_draft(client, "DOC123", timeout_seconds=5, poll_interval_seconds=2)


@patch("pandadoc_push.time.sleep")
@patch("pandadoc_push.requests.get")
def test_wait_until_draft_fails_on_error_status(mock_get, mock_sleep):
    r = Mock(ok=True)
    r.json.return_value = {"id": "DOC123", "status": "document.error"}
    mock_get.return_value = r

    client = PandaDocClient("fake-key")

    with pytest.raises(PandaDocAPIError):
        wait_until_draft(client, "DOC123")


@patch("pandadoc_push.requests.post")
def test_send_document_posts_to_send_endpoint(mock_post):
    mock_response = Mock(ok=True)
    mock_response.json.return_value = {"id": "DOC123", "status": "document.sent"}
    mock_post.return_value = mock_response

    client = PandaDocClient("fake-key")
    result = send_document(client, "DOC123")

    assert result["status"] == "document.sent"
    called_url = mock_post.call_args[0][0]
    assert called_url == "https://api.pandadoc.com/public/v1/documents/DOC123/send"
