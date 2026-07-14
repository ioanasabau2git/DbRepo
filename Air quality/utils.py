
"""OpenAQ API helpers: safe session, retries, timeouts and pagination.

Usage example:
	from utils import create_session, get_locations
	session = create_session()
	locations = get_locations(session, countries_id=74)

The module will read an API key from the environment variable `OPENAQ_API_KEY`.
If not present, it will fall back to `config.OpenAQ_API_KEY` when a local
`config.py` exists (convenient for Databricks development where secrets are
temporarily stored in a git-ignored `config.py`).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Iterator, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def _load_api_key() -> Optional[str]:
    """Return API key from env or local config fallback.

    Priority: `OPENAQ_API_KEY` env var, then `config.OpenAQ_API_KEY` if present.
    """
    key = os.getenv("OPENAQ_API_KEY")
    if key:
        return key

    try:
        # local config.py may exist but is gitignored during development
        from config import OpenAQ_API_KEY as _cfg_key  # type: ignore

        return _cfg_key
    except Exception:
        return None


def create_session(retries: int = 3, backoff_factor: float = 0.3, status_forcelist=(429, 500, 502, 503, 504)) -> requests.Session:
    """Create a `requests.Session` with a retry/backoff policy.

    Returns a configured session. Caller must still pass `timeout` to requests.
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _request_json(session: requests.Session, url: str, *, params: Optional[Dict] = None, headers: Optional[Dict] = None, timeout: float = 10.0) -> Dict:
    """Perform a GET request and return parsed JSON, with basic error handling."""
    try:
        resp = session.get(url, params=params,
                           headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        LOGGER.exception("HTTP error while requesting %s", url)
        raise
    except requests.RequestException:
        LOGGER.exception("Network error while requesting %s", url)
        raise


def fetch_paginated(session: requests.Session, base_url: str, *, params: Optional[Dict] = None, items_key: str = "results", limit: int = 100, max_pages: Optional[int] = None, timeout: float = 10.0) -> Iterator[Dict]:
    """Yield items from a paginated OpenAQ endpoint.

    The OpenAQ v3 API uses `page` and `limit` style pagination and returns
    results under a `results` key. This helper iterates pages until an empty
    page is returned or `max_pages` is reached.
    """
    if params is None:
        params = {}
    page = int(params.pop("page", 1))
    params = dict(params)  # copy to avoid mutating caller dict
    headers = {"X-API-Key": _load_api_key()} if _load_api_key() else None

    while True:
        params.update({"limit": limit, "page": page})
        LOGGER.debug("Fetching page %s from %s with params=%s",
                     page, base_url, params)
        data = _request_json(session, base_url, params=params,
                             headers=headers, timeout=timeout)
        items = data.get(items_key) or []
        if not items:
            break
        for it in items:
            yield it
        if len(items) < limit:
            break
        page += 1
        if max_pages and page > max_pages:
            LOGGER.debug(
                "Reached max_pages=%s, stopping pagination", max_pages)
            break


def get_locations(session: Optional[requests.Session] = None, *, countries_id: Optional[int] = None, limit: int = 100, max_pages: Optional[int] = None, **extra_params) -> List[Dict]:
    """Return a list of location records from OpenAQ.

    Example: `get_locations(session, countries_id=74)`
    """
    session = session or create_session()
    url = "https://api.openaq.org/v3/locations"
    params = dict(extra_params)
    if countries_id is not None:
        params["countries_id"] = countries_id
    return list(fetch_paginated(session, url, params=params, items_key="results", limit=limit, max_pages=max_pages))


def get_parameters(session: Optional[requests.Session] = None, *, limit: int = 100, max_pages: Optional[int] = None) -> List[Dict]:
    """Return the list of parameters supported by OpenAQ."""
    session = session or create_session()
    url = "https://api.openaq.org/v3/parameters"
    return list(fetch_paginated(session, url, items_key="results", limit=limit, max_pages=max_pages))


def get_sensor_measurements(session: Optional[requests.Session] = None, sensor_id: str = "", *, datetime_from: Optional[str] = None, datetime_to: Optional[str] = None, limit: int = 100, max_pages: Optional[int] = None) -> List[Dict]:
    """Get measurements for a sensor. Date times should be ISO-8601 strings.

    This uses the `sensors/{id}/measurements/hourly` endpoint as in the
    original notebooks.
    """
    if not sensor_id:
        raise ValueError("sensor_id is required")
    session = session or create_session()
    url = f"https://api.openaq.org/v3/sensors/{sensor_id}/measurements/hourly"
    params: Dict[str, object] = {}
    if datetime_from:
        params["datetime_from"] = datetime_from
    if datetime_to:
        params["datetime_to"] = datetime_to
    return list(fetch_paginated(session, url, params=params, items_key="results", limit=limit, max_pages=max_pages))


__all__ = [
    "create_session",
    "get_locations",
    "get_parameters",
    "get_sensor_measurements",
    "fetch_paginated",
]
