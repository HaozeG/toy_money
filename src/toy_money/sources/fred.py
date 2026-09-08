"""FRED (St. Louis Fed) — OPTIONAL. Used only if FRED_API_KEY is set in the env.

Not wired into the default indicator table; provided so future series can opt in
by setting source="fred" with params={"series_id": "..."}.
"""

from __future__ import annotations

import os

import pandas as pd

from ..config import Series
from ._http import get_json

BASE = "https://api.stlouisfed.org/fred/series/observations"


class FredKeyMissing(RuntimeError):
    pass


def available() -> bool:
    return bool(os.environ.get("FRED_API_KEY"))


def fetch(series: Series) -> pd.DataFrame:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise FredKeyMissing(
            "FRED_API_KEY not set; skipping FRED series. "
            "Get a free key at https://fredaccount.stlouisfed.org/apikeys"
        )
    sid = series.params["series_id"]
    country = series.params.get("country", "USA")
    payload = get_json(
        BASE, params={"series_id": sid, "api_key": key, "file_type": "json"}
    )
    rows = [
        {"country": country, "year": obs["date"][:4], "value": obs["value"]}
        for obs in payload.get("observations", [])
        if obs.get("value") not in (".", "", None)
    ]
    if not rows:
        raise RuntimeError(f"FRED returned no observations for {sid}")
    df = pd.DataFrame(rows)
    return df.groupby(["country", "year"], as_index=False)["value"].agg(
        lambda s: pd.to_numeric(s, errors="coerce").mean()
    )
