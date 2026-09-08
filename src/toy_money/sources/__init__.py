"""Data source adapters. Each exposes `fetch(series) -> pd.DataFrame[country,year,value]`."""

from __future__ import annotations

from ..config import Series
from . import bis, fred, imf, worldbank

_DISPATCH = {
    "worldbank": worldbank.fetch,
    "imf": imf.fetch,
    "bis": bis.fetch,
    "fred": fred.fetch,
}

SOURCE_NAMES = list(_DISPATCH)


def fetch(series: Series):
    if series.source == "seed":
        raise RuntimeError(f"{series.key}: seed-only series, nothing to fetch")
    return _DISPATCH[series.source](series)
