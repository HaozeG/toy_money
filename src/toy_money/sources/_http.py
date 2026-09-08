"""Shared HTTP helper with a short timeout and a descriptive User-Agent."""

from __future__ import annotations

import requests

_UA = "toy-money/0.1 (research; +https://github.com/local/toy_money)"
TIMEOUT = 30


def get_json(url: str, params: dict | None = None):
    r = requests.get(url, params=params, headers={"User-Agent": _UA}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_text(url: str, params: dict | None = None) -> str:
    r = requests.get(url, params=params, headers={"User-Agent": _UA}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text
