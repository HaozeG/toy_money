"""World Bank Indicators API v2 (keyless).

Endpoint: https://api.worldbank.org/v2/country/{iso3;iso3}/indicator/{code}
Response: [ {pagination...}, [ {countryiso3code, date, value}, ... ] ]
"""

from __future__ import annotations

import pandas as pd

from ..config import COUNTRIES, Series
from ._http import get_json

BASE = "https://api.worldbank.org/v2"


def fetch(series: Series) -> pd.DataFrame:
    code = series.params["indicator"]
    countries = ";".join(COUNTRIES)
    url = f"{BASE}/country/{countries}/indicator/{code}"
    payload = get_json(url, params={"format": "json", "per_page": 20000})
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        raise RuntimeError(f"World Bank returned no data for {code}: {payload!r:.200}")
    rows = [
        {
            "country": r.get("countryiso3code") or r["country"]["id"],
            "year": r["date"],
            "value": r["value"],
        }
        for r in payload[1]
    ]
    return pd.DataFrame(rows)
