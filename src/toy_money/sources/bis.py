"""BIS SDMX RESTful API (keyless).

Endpoint: https://stats.bis.org/api/v1/data/{flow}/{key}/all?format=csv
Returns SDMX 2.1 CSV: one column per dimension plus TIME_PERIOD and OBS_VALUE.

The dimension keys are verified against the returned SDMX CSV: `fetch` checks
the dimension columns the API echoes back (country, borrower type, valuation,
unit) and raises if the key resolved to something other than the intended
series. That is stricter than "the request returned rows", though a full
semantic check against BIS metadata still requires a human review when a new
flow is added.

Quarterly observations are collapsed to an annual mean.
"""

from __future__ import annotations

import io

import pandas as pd

import sys

from ..config import FETCH_COUNTRIES, Series
from ._http import get_text

BASE = "https://stats.bis.org/api/v1/data"

# Total-credit flow (WS_TC): credit to the non-financial sector, % of GDP.
# key layout: FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE
_TC_KEY = "Q.{cty}.{borrowers}.A.M.770"
# Selected property prices (WS_SPP): FREQ.REF_AREA.VALUE.UNIT_MEASURE
_SPP_KEY = "Q.{cty}.R.628"

# BIS uses ISO-3166 alpha-2. Taiwan is not a BIS reporting economy for WS_TC /
# WS_SPP; it is listed so `request_urls` is complete, and the fetch records it as
# a coverage gap rather than raising.
_ISO2 = {
    "CHN": "CN", "JPN": "JP", "FIN": "FI", "SWE": "SE", "KOR": "KR",
    "USA": "US", "GBR": "GB", "ESP": "ES", "IRL": "IE",
    "TWN": "TW", "DEU": "DE", "ITA": "IT",
}


def _expected_dimensions(dataset: str, cty: str, borrowers: str) -> dict[str, str]:
    if dataset == "WS_SPP":
        return {"FREQ": "Q", "REF_AREA": cty, "VALUE": "R", "UNIT_MEASURE": "628"}
    return {
        "FREQ": "Q",
        "BORROWERS_CTY": cty,
        "TC_BORROWERS": borrowers,
        "TC_LENDERS": "A",
        "VALUATION": "M",
        "UNIT_TYPE": "770",
    }


def _validate_dimensions(flow: str, raw: pd.DataFrame, expected: dict[str, str]) -> None:
    """Ensure the returned SDMX CSV matches the key we asked for."""
    cols = {str(c).upper(): c for c in raw.columns}
    found: list[str] = []
    mismatches: list[str] = []
    for dim, want in expected.items():
        col = cols.get(dim.upper())
        if col is None:
            continue
        found.append(dim)
        values = raw[col].dropna().astype(str).str.strip().unique()
        if len(values) != 1 or values[0] != str(want):
            mismatches.append(f"{dim}={values.tolist()} (expected {want!r})")
    missing = [dim for dim in expected if dim not in found]
    if mismatches:
        raise RuntimeError(
            f"BIS {flow}: query key did not resolve to the intended series: "
            + "; ".join(mismatches)
        )
    if missing:
        raise RuntimeError(
            f"BIS {flow}: missing expected dimension columns {missing}; "
            f"got {list(raw.columns)}"
        )


def _key_for(dataset: str, iso3: str, borrowers: str) -> str:
    cty = _ISO2[iso3]
    if dataset == "WS_SPP":
        return _SPP_KEY.format(cty=cty)
    return _TC_KEY.format(cty=cty, borrowers=borrowers)


def request_urls(series: Series) -> list[tuple[str, str]]:
    """(country, full CSV request URL) for each country — for `toy-money verify`."""
    dataset = series.params.get("dataset", "WS_TC")
    borrowers = series.params.get("borrowers", "P")
    urls = []
    for iso3 in FETCH_COUNTRIES:
        key = _key_for(dataset, iso3, borrowers)
        urls.append((iso3, f"{BASE}/{dataset}/{key}/all?format=csv"))
    return urls


def _fetch_one(flow: str, key: str, expected: dict[str, str]) -> pd.DataFrame:
    url = f"{BASE}/{flow}/{key}/all"
    text = get_text(url, params={"format": "csv"})
    raw = pd.read_csv(io.StringIO(text))
    _validate_dimensions(flow, raw, expected)
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
    borrowers = series.params.get("borrowers", "P")
    frames = []
    missing: list[str] = []
    for iso3 in FETCH_COUNTRIES:
        cty = _ISO2[iso3]
        key = _key_for(dataset, iso3, borrowers)
        expected = _expected_dimensions(dataset, cty, borrowers)
        try:
            df = _fetch_one(dataset, key, expected)
        except Exception as exc:  # noqa: BLE001
            # A wrong dimension *value* (the key resolved to the wrong series) is
            # a real bug — re-raise. An economy simply absent from the flow
            # (e.g. TWN, or an EME not in WS_SPP — HTTP 404 / empty CSV) is a
            # coverage gap: record it, keep the other countries, let the analyzer
            # mark the indicator unavailable for that episode.
            if any(
                m in str(exc)
                for m in (
                    "did not resolve to the intended series",
                    "missing expected dimension columns",
                )
            ):
                raise
            missing.append(f"{iso3}: {exc}")
            continue
        df["country"] = iso3
        frames.append(df[["country", "year", "value"]])
    if missing:
        print(
            f"  note  BIS {dataset} {series.key}: no data for "
            + ", ".join(missing),
            file=sys.stderr,
        )
    if not frames:
        raise RuntimeError(f"BIS returned no rows for {dataset} {series.key}")
    return pd.concat(frames, ignore_index=True)
