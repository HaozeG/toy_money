"""BIS SDMX RESTful API (keyless).

Endpoint: https://stats.bis.org/api/v1/data/{flow}/{key}/all?format=csv
Returns SDMX 2.1 CSV: one column per dimension plus TIME_PERIOD and OBS_VALUE.

The exact dimension keys below are best-effort and marked VERIFY in config.py —
confirm against https://stats.bis.org before trusting fetched values. When the
query key is wrong the API returns 404/empty and `fetch` raises, so `toy-money
fetch` falls back to the bundled seed CSV.

Quarterly observations are collapsed to an annual mean.
"""

from __future__ import annotations

import io

import pandas as pd

from ..config import COUNTRIES, Series
from ._http import get_text

BASE = "https://stats.bis.org/api/v1/data"

# Total-credit flow (WS_TC): credit to the non-financial sector, % of GDP.
# key layout: FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE
_TC_KEY = "Q.{cty}.{borrowers}.A.M.770"
# Selected property prices (WS_SPP): FREQ.REF_AREA.VALUE.UNIT_MEASURE
_SPP_KEY = "Q.{cty}.R.628"

_ISO2 = {"CHN": "CN", "JPN": "JP"}


def _fetch_one(flow: str, key: str) -> pd.DataFrame:
    url = f"{BASE}/{flow}/{key}/all"
    text = get_text(url, params={"format": "csv"})
    raw = pd.read_csv(io.StringIO(text))
    cols = {c.upper(): c for c in raw.columns}
    time_col = cols.get("TIME_PERIOD") or cols.get("TIME")
    val_col = cols.get("OBS_VALUE") or cols.get("VALUE")
    if not time_col or not val_col:
        raise RuntimeError(f"BIS {flow}: unexpected CSV columns {list(raw.columns)}")
    out = raw[[time_col, val_col]].rename(columns={time_col: "period", val_col: "value"})
    out["year"] = out["period"].astype(str).str.slice(0, 4)
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["year", "value"])
    if out.empty:
        raise RuntimeError(
            f"BIS {flow} key='{key}': matched {len(raw)} rows but none parsed to "
            f"(year, value). Columns: {list(raw.columns)}"
        )
    out["year"] = out["year"].astype(int)
    return out.groupby("year", as_index=False)["value"].mean()


def fetch(series: Series) -> pd.DataFrame:
    dataset = series.params.get("dataset", "WS_TC")
    frames = []
    for iso3 in COUNTRIES:
        cty = _ISO2[iso3]
        if dataset == "WS_SPP":
            key = _SPP_KEY.format(cty=cty)
        else:
            key = _TC_KEY.format(cty=cty, borrowers=series.params.get("borrowers", "P"))
        df = _fetch_one(dataset, key)
        df["country"] = iso3
        frames.append(df[["country", "year", "value"]])
    combined = pd.concat(frames, ignore_index=True)
    if combined.empty:
        raise RuntimeError(f"BIS returned no rows for {dataset} {series.key}")
    return combined
