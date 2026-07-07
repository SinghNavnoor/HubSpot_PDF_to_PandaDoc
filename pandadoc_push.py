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


def push_and_send(
    docx_path: Path | str,
    api_key: str,
    recipient_name: str,
    recipient_email: str,
    document_name: str | None = None,
) -> str:
    """Full Phase 3: upload, wait for processing, send. Returns document id."""
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
