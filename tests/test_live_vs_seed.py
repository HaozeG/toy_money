"""Regression guard: live-fetched values vs. the committed seed snapshot.

What it catches: a provider silently rebasing or revising a series, or a change
to `sources/*` / `config.py` that shifts what a key returns. On such a change the
live parquet drifts from `seed/seed.csv` (a snapshot of an earlier fetch) past the
tolerance and the run fails — a signal to look, not a network error.

What it does NOT catch: a key that was wrong from the start. The seed is produced
by the same fetch code with the same keys, so an always-wrong key sits in both
sides and passes. The dimension *choice* is checked once per series by
`toy-money verify` (a human against stats.bis.org); the *values echoed back* are
checked every fetch by `sources/bis.py`.

Skips when there is no live cache (`data/` absent) — a no-op in the default CI and
locally until `toy-money pull-cache` has run; wired into `refresh-data.yml`.
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
def test_live_matches_snapshot(series):
    live = datastore.read(series.key)  # parquet (provenance was "live" in the filter)
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
        f"{series.key}: {len(bad)} of {len(merged)} points drifted from the seed "
        f"snapshot beyond tolerance — a provider revision or a code/key change:\n"
        + bad[["country", "year", "value_live", "value_seed"]].to_string(index=False)
    )
