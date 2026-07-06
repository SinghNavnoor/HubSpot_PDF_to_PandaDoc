"""Thin authenticated HTTP client for the HubSpot CRM v3 API."""
from __future__ import annotations

import requests

HUBSPOT_API_BASE = "https://api.hubapi.com"


class HubSpotAPIError(Exception):
    """Raised when the HubSpot API returns a non-2xx response."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HubSpot API error {status_code}: {body}")


class HubSpotClient:
    """Minimal authenticated client for HubSpot CRM v3 endpoints."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("HubSpot API key is required")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def get(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(
            f"{HUBSPOT_API_BASE}{path}",
            headers=self._headers,
            params=params,
            timeout=30,
        )
        return self._parse(response)

    def post(self, path: str, json_body: dict) -> dict:
        response = requests.post(
            f"{HUBSPOT_API_BASE}{path}",
            headers=self._headers,
            json=json_body,
            timeout=30,
        )
        return self._parse(response)

    @staticmethod
    def _parse(response: requests.Response) -> dict:
        if not response.ok:
            raise HubSpotAPIError(response.status_code, response.text)
        return response.json()
