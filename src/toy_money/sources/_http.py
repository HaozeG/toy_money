"""Shared HTTP helper: short timeout, descriptive User-Agent, light retry."""

from __future__ import annotations

import time

import requests

_UA = "toy-money/0.1 (research; +https://github.com/HaozeG/toy_money)"
TIMEOUT = 60
_RETRIES = 4


def _request(url: str, params: dict | None):
    last = None
    for attempt in range(_RETRIES):
        try:
            r = requests.get(
                url, params=params, headers={"User-Agent": _UA}, timeout=TIMEOUT
            )
            # World Bank / IMF intermittently 400/429/5xx under load; retry those.
            if r.status_code in (400, 429, 500, 502, 503, 504):
                last = requests.HTTPError(f"{r.status_code} for {r.url}")
                raise last
            r.raise_for_status()
            return r
        except (requests.RequestException,) as exc:  # noqa: PERF203
            last = exc
            if attempt < _RETRIES - 1:
                time.sleep(2 ** attempt)
    raise last


def get_json(url: str, params: dict | None = None):
    return _request(url, params).json()


def get_text(url: str, params: dict | None = None) -> str:
    return _request(url, params).text
