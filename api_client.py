"""API client for Linux Mint Hub.

OmniStream is used only for authentication and stats tracking.
All marketplace calls go directly to the Mint Hub backend.
"""

import json
from typing import Any, Optional

import requests

from constants import OMNISTREAM_BASE, MINT_HUB_BASE, API_SLUG


class OmniError(Exception):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.status = status


class OmniClient:
    """Handles OmniStream auth validation and stats tracking only."""

    def __init__(self, token: str, base: str = OMNISTREAM_BASE, timeout: float = 15.0):
        self._token = token
        self._base = base.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"accept": "application/json"})

    def validate_key(self) -> bool:
        try:
            resp = self._session.get(
                f"{self._base}/v1/apis",
                headers={"x-omni-key": self._token},
                timeout=self._timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def track_stat(self, event: str, data: dict = None):
        try:
            self._session.post(
                f"{self._base}/v1/call/{API_SLUG}/track",
                json={"body": {"event": event, **(data or {})}},
                headers={"x-omni-key": self._token},
                timeout=5,
            )
        except Exception:
            pass

    def close(self):
        self._session.close()


class MintHubClient:
    """Direct client for the Mint Hub marketplace API."""

    def __init__(self, omni_key: str, base: str = MINT_HUB_BASE):
        self._key = omni_key
        self._base = base.rstrip("/")
        self._omni = OmniClient(omni_key)
        self._session = requests.Session()
        self._session.headers.update({
            "accept": "application/json",
            "x-api-key": omni_key,
        })
        self._timeout = 30.0

    def validate_key(self) -> bool:
        return self._omni.validate_key()

    def _request(self, method: str, path: str, params: dict = None,
                 json_body: Any = None, timeout: float = None) -> Any:
        url = f"{self._base}{path}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        resp = self._session.request(
            method, url,
            params=clean_params,
            json=json_body,
            timeout=timeout or self._timeout,
        )
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code >= 400:
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                raise OmniError(err.get("code", str(resp.status_code)),
                                err.get("message", "Request failed"), resp.status_code)
            raise OmniError(str(resp.status_code), resp.text or "Request failed", resp.status_code)
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    def list_enhancements(self, category: str = None, sort: str = "trending",
                          page: int = 1, per_page: int = 30, q: str = None) -> dict:
        return self._request("GET", "/enhancements", params={
            "category": category, "sort": sort, "page": page, "per_page": per_page, "q": q,
        })

    def get_enhancement(self, slug: str) -> dict:
        return self._request("GET", f"/enhancements/{slug}")

    def download(self, slug: str) -> dict:
        return self._request("GET", f"/enhancements/{slug}/download")

    def upload(self, data: dict) -> dict:
        return self._request("POST", "/enhancements", json_body=data)

    def search(self, query: str, category: str = None, limit: int = 30) -> dict:
        return self._request("GET", "/enhancements/search", params={
            "q": query, "category": category, "limit": limit,
        })

    def get_trending(self) -> list:
        return self._request("GET", "/enhancements/trending")

    def get_featured(self) -> list:
        return self._request("GET", "/enhancements/featured")

    def get_new(self) -> list:
        return self._request("GET", "/enhancements/new")

    def list_categories(self) -> list:
        return self._request("GET", "/categories")

    def get_stats(self) -> dict:
        return self._request("GET", "/stats")

    def list_reviews(self, slug: str) -> list:
        return self._request("GET", f"/enhancements/{slug}/reviews")

    def submit_review(self, slug: str, rating: int, comment: str,
                      username: str, title: str = "") -> dict:
        return self._request("POST", f"/enhancements/{slug}/reviews", json_body={
            "rating": rating, "comment": comment, "username": username, "title": title,
        })

    def list_collections(self) -> list:
        return self._request("GET", "/collections")

    def get_collection(self, collection_id: str) -> dict:
        return self._request("GET", f"/collections/{collection_id}")

    def my_uploads(self) -> list:
        return self._request("GET", "/me/uploads")

    def my_downloads(self) -> list:
        return self._request("GET", "/me/downloads")

    def get_thumbnail_url(self, slug: str) -> str:
        return f"{self._base}/enhancements/{slug}/thumbnail"

    def track(self, event: str, data: dict = None):
        self._omni.track_stat(event, data)

    def close(self):
        self._session.close()
        self._omni.close()
