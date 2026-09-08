"""IMF DataMapper API v1 (keyless).

Endpoint: https://www.imf.org/external/datamapper/api/v1/{indicator}/{iso3}/{iso3}
Response: {"values": {indicator: {iso3: {"1990": 12.3, ...}}}}
"""

from __future__ import annotations

import pandas as pd

from ..config import COUNTRIES, Series
from ._http import get_json

BASE = "https://www.imf.org/external/datamapper/api/v1"


def fetch(series: Series) -> pd.DataFrame:
    ind = series.params["indicator"]
    url = f"{BASE}/{ind}/" + "/".join(COUNTRIES)
    payload = get_json(url)
    block = (payload.get("values") or {}).get(ind) or {}
    if not block:
        raise RuntimeError(f"IMF returned no data for {ind}: {payload!r:.200}")
    rows = [
        {"country": iso, "year": year, "value": val}
        for iso, byyear in block.items()
        if iso in COUNTRIES
        for year, val in byyear.items()
    ]
    if not rows:
        raise RuntimeError(f"IMF: no {ind} rows for {list(COUNTRIES)}")
    return pd.DataFrame(rows)
