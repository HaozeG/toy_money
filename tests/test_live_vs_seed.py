"""Live-fetched values vs. the bundled seed snapshot.

An Action fetch exiting 0 means HTTP succeeded and rows parsed — it does *not*
prove the BIS SDMX key selected the intended series. This test compares the live
parquet against the hand-checked seed at overlapping (country, year) points; a
failure here is a wrong-key / wrong-series signal, not a network signal.

Skips cleanly when there is no live cache (`data/` absent), so it is a no-op in
the default CI and locally until `toy-money pull-cache` has run.
"""

from __future__ import annotations

import pytest

from toy_money import datastore
from toy_money.config import SERIES

# Growth-rate / share series: compare on an absolute pp tolerance (revisions move
# these by a few tenths). Everything else: 10% relative.
_ABSOLUTE_PP = {
    "gdp_growth": 1.5,
    "cpi_inflation": 1.5,
    "workingage_share": 1.5,
    "youth_unemployment": 1.5,
}
_REL = 0.10
_MAX_OUTLIERS = 1  # one point may disagree (a single revised vintage)


def _live_series():
    return [
        s
        for s in SERIES
        if datastore.provenance(s.key) == "live"
        and datastore.seed_frame(s.key) is not None
    ]


_LIVE = _live_series()
pytestmark = pytest.mark.skipif(
    not _LIVE, reason="no live cache — run `toy-money pull-cache` first"
)


@pytest.mark.parametrize("series", _LIVE or SERIES[:1], ids=lambda s: s.key)
def test_live_matches_seed(series):
    live = datastore.read(series.key)  # parquet (has() was true in the filter)
    seed = datastore.seed_frame(series.key)
    merged = live.merge(
        seed, on=["country", "year"], suffixes=("_live", "_seed"), how="inner"
    )
    assert not merged.empty, f"{series.key}: no overlapping (country, year) points"

    tol_pp = _ABSOLUTE_PP.get(series.key)
    if tol_pp is not None:
        bad = merged[(merged.value_live - merged.value_seed).abs() > tol_pp]
    else:
        denom = merged.value_seed.abs().clip(lower=1e-9)
        bad = merged[
            (merged.value_live - merged.value_seed).abs() / denom > _REL
        ]

    assert len(bad) <= _MAX_OUTLIERS, (
        f"{series.key}: {len(bad)} of {len(merged)} points disagree beyond "
        f"tolerance — possible wrong series/key:\n"
        + bad[["country", "year", "value_live", "value_seed"]].to_string(index=False)
    )
