#!/usr/bin/env python3
"""
Push the combined check-request DOCX to PandaDoc and send it for signature.

Uploads the DOCX, assigns two recipients in signing order (Senior Housing
Program Manager first, then Program Director), places signature fields via
the layout API, and auto-sends.
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

from csv_to_word_forms import (
    PANDADOC_SENIOR_HOUSING_PM_ROLE,
    PANDADOC_SIGNATURE_ROLE,
)

PANDADOC_API_BASE = "https://api.pandadoc.com"
DOCUMENTS_PATH = "/public/v1/documents"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_POLL_INTERVAL_SECONDS = 2

DRAFT_STATUS = "document.draft"
ERROR_STATUSES = {"document.error", "document.declined", "document.voided"}

# Director signature + signing-date on each check-request page (not the cover).
PANDADOC_PAGE_WIDTH = 600
PANDADOC_PAGE_HEIGHT = 850
SIGNATURE_X_FRACTION = 0.2
SIGNATURE_Y_FRACTION = 0.99
DATE_X_FRACTION = 0.78
SIGNATURE_WIDTH = 120
SIGNATURE_HEIGHT = 33
DATE_WIDTH = 90
DATE_HEIGHT = 22
# Cover page — SH Program Manager acknowledgment signature (page 1).
COVER_SIGNATURE_X_FRACTION = 0.2
COVER_SIGNATURE_Y_FRACTION = 0.55
SIGNATURE_FIELDS_CHUNK_SIZE = 25

REQUIRED_FIELD_SETTINGS = {"required": True}
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


def _recipient_payload(
    name: str,
    email: str,
    role: str,
    signing_order: int,
) -> dict:
    first_name, last_name = _split_name(name)
    return {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "role": role,
        "signing_order": signing_order,
    }


def create_document_from_docx(
    client: PandaDocClient,
    docx_path: Path | str,
    document_name: str,
    shpm_name: str,
    shpm_email: str,
    director_name: str,
    director_email: str,
) -> str:
    """
    Upload the DOCX with two recipients in signing order:
    1 — Senior Housing Program Manager (cover page)
    2 — Program Director (each check-request form)
    """
    docx_path = Path(docx_path)
    payload = {
        "name": document_name,
        "parse_form_fields": False,
        "recipients": [
            _recipient_payload(
                shpm_name, shpm_email, PANDADOC_SENIOR_HOUSING_PM_ROLE, 1
            ),
            _recipient_payload(
                director_name, director_email, PANDADOC_SIGNATURE_ROLE, 2
            ),
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


def get_recipient_id_by_role(details: dict, role: str) -> str:
    """Return a recipient UUID matching the PandaDoc role name."""
    for recipient in details.get("recipients") or []:
        if recipient.get("role") == role:
            recipient_id = recipient.get("id")
            if recipient_id:
                return recipient_id
    raise PandaDocAPIError(0, f"No recipient with role {role!r} on document")


def get_primary_recipient_id(details: dict) -> str:
    """Return the first recipient id (legacy helper)."""
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


def signature_field_payload(
    page: int,
    recipient_id: str,
    *,
    x_fraction: float = SIGNATURE_X_FRACTION,
    y_fraction: float = SIGNATURE_Y_FRACTION,
) -> dict:
    """One signature field on a page at the configured layout."""
    return {
        "type": "signature",
        "assigned_to": recipient_id,
        "settings": REQUIRED_FIELD_SETTINGS,
        "layout": _field_layout(
            page,
            x_fraction,
            y_fraction,
            SIGNATURE_WIDTH,
            SIGNATURE_HEIGHT,
        ),
    }


def date_field_payload(page: int, recipient_id: str) -> dict:
    """Signing-date field beside the Director signature."""
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


def shpm_cover_signature_field_payload(page: int, recipient_id: str) -> dict:
    """SH Program Manager acknowledgment signature on the cover page."""
    return signature_field_payload(
        page,
        recipient_id,
        x_fraction=COVER_SIGNATURE_X_FRACTION,
        y_fraction=COVER_SIGNATURE_Y_FRACTION,
    )


def director_fields_for_page(page: int, recipient_id: str) -> list[dict]:
    """Director signature + signing-date on one check-request page."""
    return [
        signature_field_payload(page, recipient_id),
        date_field_payload(page, recipient_id),
    ]


def build_batch_signature_fields(
    total_page_count: int,
    shpm_recipient_id: str,
    director_recipient_id: str,
    *,
    has_cover_page: bool = True,
) -> list[dict]:
    """All PandaDoc fields: cover SHPM signature + director fields on form pages."""
    if total_page_count < 1:
        raise ValueError("total_page_count must be at least 1")

    fields: list[dict] = []
    first_form_page = 1
    if has_cover_page:
        fields.append(shpm_cover_signature_field_payload(1, shpm_recipient_id))
        first_form_page = 2

    for page in range(first_form_page, total_page_count + 1):
        fields.extend(director_fields_for_page(page, director_recipient_id))
    return fields


def place_signature_fields(
    client: PandaDocClient,
    document_id: str,
    page_count: int,
    shpm_recipient_id: str | None = None,
    director_recipient_id: str | None = None,
    *,
    has_cover_page: bool = True,
) -> int:
    """
    Place cover + Director signature fields via PandaDoc's fields API.
    page_count is total pages (cover + one page per HubSpot deal).
    """
    details = get_document_details(client, document_id)
    if shpm_recipient_id is None:
        shpm_recipient_id = get_recipient_id_by_role(
            details, PANDADOC_SENIOR_HOUSING_PM_ROLE
        )
    if director_recipient_id is None:
        director_recipient_id = get_recipient_id_by_role(
            details, PANDADOC_SIGNATURE_ROLE
        )

    all_fields = build_batch_signature_fields(
        page_count,
        shpm_recipient_id,
        director_recipient_id,
        has_cover_page=has_cover_page,
    )

    created = 0
    for start in range(0, len(all_fields), SIGNATURE_FIELDS_CHUNK_SIZE):
        chunk = all_fields[start : start + SIGNATURE_FIELDS_CHUNK_SIZE]
        response = requests.post(
            f"{PANDADOC_API_BASE}{DOCUMENTS_PATH}/{document_id}/fields",
            headers={**client.headers, "Content-Type": "application/json"},
            json={"fields": chunk},
            timeout=120,
        )
        _parse(response)
        created += len(chunk)

    return created


def push_and_send(
    docx_path: Path | str,
    api_key: str,
    shpm_name: str,
    shpm_email: str,
    director_name: str,
    director_email: str,
    document_name: str | None = None,
    page_count: int | None = None,
    *,
    use_api_signature_placement: bool = True,
    has_cover_page: bool = True,
) -> str:
    """Full Phase 3: upload, wait for processing, place signatures, send."""
    docx_path = Path(docx_path)
    if not docx_path.is_file():
        raise FileNotFoundError(f"Combined DOCX not found: {docx_path}")
    if not shpm_email:
        raise ValueError(
            "Senior Housing Program Manager email is required "
            "(SENIOR_HOUSING_PROGRAM_MANAGER_EMAIL)"
        )
    if not director_email:
        raise ValueError("Program Director email is required (PROGRAM_DIRECTOR_EMAIL)")

    client = PandaDocClient(api_key)
    name = document_name or f"Check Requests Combined {date.today().isoformat()}"

    document_id = create_document_from_docx(
        client,
        docx_path,
        name,
        shpm_name,
        shpm_email,
        director_name,
        director_email,
    )
    print(f"Uploaded to PandaDoc: document id {document_id}")

    wait_until_draft(client, document_id)
    print("Document processed (draft).")

    if use_api_signature_placement:
        if not page_count:
            raise ValueError("page_count is required for API signature placement")
        count = place_signature_fields(
            client, document_id, page_count, has_cover_page=has_cover_page
        )
        print(
            f"Placed {count} field(s) (cover SHPM + director signature/date per form) "
            "via PandaDoc layout API."
        )

    send_document(client, document_id)
    print(
        f"Sent for signature: {shpm_email} (order 1), then {director_email} (order 2)."
    )
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
            shpm_name=os.environ.get("SENIOR_HOUSING_PROGRAM_MANAGER_NAME", ""),
            shpm_email=os.environ.get("SENIOR_HOUSING_PROGRAM_MANAGER_EMAIL", ""),
            director_name=os.environ.get("PROGRAM_DIRECTOR_NAME", ""),
            director_email=os.environ.get("PROGRAM_DIRECTOR_EMAIL", ""),
        )
    except (PandaDocAPIError, TimeoutError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
