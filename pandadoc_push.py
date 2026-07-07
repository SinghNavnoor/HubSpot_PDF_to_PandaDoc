#!/usr/bin/env python3
"""
Push the combined check-request DOCX to PandaDoc and send it for signature.

Uploads the DOCX via PandaDoc's create-document-from-file API (field tags in
the document are parsed into real fields), assigns the fixed Program Director
recipient to the signature role, waits for processing, then auto-sends.

Failures are loud (non-zero exit, clear message) — this is run by hand and
watched, per the design spec's error-handling rules.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

from csv_to_word_forms import PANDADOC_SIGNATURE_ROLE

PANDADOC_API_BASE = "https://api.pandadoc.com"
DOCUMENTS_PATH = "/public/v1/documents"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_POLL_INTERVAL_SECONDS = 2

DRAFT_STATUS = "document.draft"
ERROR_STATUSES = {"document.error", "document.declined", "document.voided"}

# Director signature + signing-date placement on each page (PandaDoc layout API).
# Signing date uses per-field settings.autofilled on API-created date fields only —
# do NOT enable workspace-wide "Autofill with signing date" (other templates need
# manual date fields, e.g. date of birth).
PANDADOC_PAGE_WIDTH = 600
PANDADOC_PAGE_HEIGHT = 850
# Grid reference (1–10 scale): signature X=2, date X=8, row Y=9.9
SIGNATURE_X_FRACTION = 0.2
SIGNATURE_Y_FRACTION = 0.99
DATE_X_FRACTION = 0.78
SIGNATURE_WIDTH = 120
SIGNATURE_HEIGHT = 33
DATE_WIDTH = 90
DATE_HEIGHT = 22
SIGNATURE_FIELDS_CHUNK_SIZE = 25  # two fields per page (signature + date)

REQUIRED_FIELD_SETTINGS = {"required": True}
# `autofilled` enables PandaDoc's signing-date autofill on date fields (see
# list fields response: settings.autofilled). Fills when the recipient signs.
DATE_FIELD_SETTINGS = {
    "required": True,
    "autofilled": True,
}


class PandaDocAPIError(Exception):
    """Raised when the PandaDoc API returns a non-2xx response or error status."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"PandaDoc API error {status_code}: {body}")


class PandaDocClient:
    """Holds auth headers for PandaDoc public API calls."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("PandaDoc API key is required")
        self.headers = {"Authorization": f"API-Key {api_key}"}


def _parse(response: requests.Response) -> dict:
    if not response.ok:
        raise PandaDocAPIError(response.status_code, response.text)
    return response.json()


def _split_name(full_name: str) -> tuple[str, str]:
    """Split 'Jane Director' into ('Jane', 'Director'); single names get empty last."""
    parts = (full_name or "").strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def create_document_from_docx(
    client: PandaDocClient,
    docx_path: Path | str,
    document_name: str,
    recipient_name: str,
    recipient_email: str,
) -> str:
    """
    Upload the DOCX and create a PandaDoc document with the Program Director
    assigned to the signature-tag role. Returns the new document's id.
    """
    docx_path = Path(docx_path)
    first_name, last_name = _split_name(recipient_name)
    payload = {
        "name": document_name,
        # False so PandaDoc parses our embedded field tags, not PDF form fields.
        "parse_form_fields": False,
        "recipients": [
            {
                "email": recipient_email,
                "first_name": first_name,
                "last_name": last_name,
                "role": PANDADOC_SIGNATURE_ROLE,
            }
        ],
    }

    with open(docx_path, "rb") as fh:
        response = requests.post(
            f"{PANDADOC_API_BASE}{DOCUMENTS_PATH}",
            headers=client.headers,
            data={"data": json.dumps(payload)},
            files={"file": (docx_path.name, fh, DOCX_MIME)},
            timeout=120,
        )
    return _parse(response)["id"]


def get_document_status(client: PandaDocClient, document_id: str) -> str:
    response = requests.get(
        f"{PANDADOC_API_BASE}{DOCUMENTS_PATH}/{document_id}",
        headers=client.headers,
        timeout=30,
    )
    return _parse(response)["status"]


def wait_until_draft(
    client: PandaDocClient,
    document_id: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
) -> None:
    """Poll until the uploaded document finishes processing (status draft)."""
    waited = 0
    while True:
        status = get_document_status(client, document_id)
        if status == DRAFT_STATUS:
            return
        if status in ERROR_STATUSES:
            raise PandaDocAPIError(
                0, f"Document {document_id} entered status {status!r} while processing"
            )
        if waited >= timeout_seconds:
            raise TimeoutError(
                f"Document {document_id} still {status!r} after {timeout_seconds}s"
            )
        time.sleep(poll_interval_seconds)
        waited += poll_interval_seconds


def send_document(client: PandaDocClient, document_id: str) -> dict:
    """Send the processed document for e-signature (no manual click needed)."""
    response = requests.post(
        f"{PANDADOC_API_BASE}{DOCUMENTS_PATH}/{document_id}/send",
        headers=client.headers,
        json={"silent": False},
        timeout=30,
    )
    return _parse(response)


def get_document_details(client: PandaDocClient, document_id: str) -> dict:
    response = requests.get(
        f"{PANDADOC_API_BASE}{DOCUMENTS_PATH}/{document_id}/details",
        headers=client.headers,
        timeout=60,
    )
    return _parse(response)


def get_primary_recipient_id(details: dict) -> str:
    """Return the first recipient id from document details."""
    recipients = details.get("recipients") or []
    if not recipients:
        raise PandaDocAPIError(0, "Document has no recipients")
    recipient_id = recipients[0].get("id")
    if not recipient_id:
        raise PandaDocAPIError(0, "Recipient id missing from document details")
    return recipient_id


def _field_layout(
    page: int,
    x_fraction: float,
    y_fraction: float,
    width: int,
    height: int,
) -> dict:
    return {
        "page": page,
        "position": {
            "offset_x": round(PANDADOC_PAGE_WIDTH * x_fraction, 2),
            "offset_y": round(PANDADOC_PAGE_HEIGHT * y_fraction, 2),
            "anchor_point": "topleft",
        },
        "style": {
            "width": width,
            "height": height,
        },
    }


def signature_field_payload(page: int, recipient_id: str) -> dict:
    """One Director signature field on a single page at the configured layout."""
    return {
        "type": "signature",
        "assigned_to": recipient_id,
        "settings": REQUIRED_FIELD_SETTINGS,
        "layout": _field_layout(
            page,
            SIGNATURE_X_FRACTION,
            SIGNATURE_Y_FRACTION,
            SIGNATURE_WIDTH,
            SIGNATURE_HEIGHT,
        ),
    }


def date_field_payload(page: int, recipient_id: str) -> dict:
    """
    Signing-date field beside the Director signature (right column).

    Uses PandaDoc's signing-date autofill (`settings.autofilled`) so the date
    reflects when the director signs, not the HubSpot create date.
    """
    return {
        "type": "date",
        "assigned_to": recipient_id,
        "settings": DATE_FIELD_SETTINGS,
        "layout": _field_layout(
            page,
            DATE_X_FRACTION,
            SIGNATURE_Y_FRACTION,
            DATE_WIDTH,
            DATE_HEIGHT,
        ),
    }


def director_fields_for_page(page: int, recipient_id: str) -> list[dict]:
    """Signature + signing-date fields for one page."""
    return [
        signature_field_payload(page, recipient_id),
        date_field_payload(page, recipient_id),
    ]


def place_signature_fields(
    client: PandaDocClient,
    document_id: str,
    page_count: int,
    recipient_id: str | None = None,
) -> int:
    """
    Place Director signature and signing-date fields on each page via PandaDoc's
    fields API. Returns the number of fields created.
    """
    if page_count < 1:
        raise ValueError("page_count must be at least 1")

    if recipient_id is None:
        details = get_document_details(client, document_id)
        recipient_id = get_primary_recipient_id(details)

    created = 0
    for start in range(1, page_count + 1, SIGNATURE_FIELDS_CHUNK_SIZE):
        end = min(start + SIGNATURE_FIELDS_CHUNK_SIZE, page_count + 1)
        fields = [
            field
            for page in range(start, end)
            for field in director_fields_for_page(page, recipient_id)
        ]
        response = requests.post(
            f"{PANDADOC_API_BASE}{DOCUMENTS_PATH}/{document_id}/fields",
            headers={**client.headers, "Content-Type": "application/json"},
            json={"fields": fields},
            timeout=120,
        )
        _parse(response)
        created += len(fields)

    return created


def push_and_send(
    docx_path: Path | str,
    api_key: str,
    recipient_name: str,
    recipient_email: str,
    document_name: str | None = None,
    page_count: int | None = None,
    *,
    use_api_signature_placement: bool = True,
) -> str:
    """Full Phase 3: upload, wait for processing, place signatures, send."""
    docx_path = Path(docx_path)
    if not docx_path.is_file():
        raise FileNotFoundError(f"Combined DOCX not found: {docx_path}")
    if not recipient_email:
        raise ValueError("Program Director email is required (PROGRAM_DIRECTOR_EMAIL)")

    client = PandaDocClient(api_key)
    name = document_name or f"Check Requests Combined {date.today().isoformat()}"

    document_id = create_document_from_docx(
        client, docx_path, name, recipient_name, recipient_email
    )
    print(f"Uploaded to PandaDoc: document id {document_id}")

    wait_until_draft(client, document_id)
    print("Document processed (draft).")

    if use_api_signature_placement:
        if not page_count:
            raise ValueError("page_count is required for API signature placement")
        count = place_signature_fields(client, document_id, page_count)
        print(
            f"Placed {count} field(s) (signature + signing date per page) "
            "via PandaDoc layout API."
        )

    send_document(client, document_id)
    print(f"Sent for signature to {recipient_email}.")
    return document_id


def main() -> int:
    load_dotenv()
    docx_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "Output/Check_Requests_Combined.docx"
    )
    try:
        push_and_send(
            docx_path,
            api_key=os.environ.get("PANDADOC_API_KEY", ""),
            recipient_name=os.environ.get("PROGRAM_DIRECTOR_NAME", ""),
            recipient_email=os.environ.get("PROGRAM_DIRECTOR_EMAIL", ""),
        )
    except (PandaDocAPIError, TimeoutError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
