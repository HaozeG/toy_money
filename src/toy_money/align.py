"""Anchor logic: re-express each country's series on a shared
"years since anchor" axis so Japan and China curves overlay directly.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import datastore
from .config import ANCHOR_PRESETS, COUNTRIES, MAX_YEAR, episode_window


@dataclass(frozen=True)
class Alignment:
    anchors: dict  # ISO3 -> anchor year
    label: str
    rule: str = "explicit"  # anchor rule that produced the years

    def describe(self) -> str:
        parts = [f"{COUNTRIES.get(k, k)} {v}" for k, v in self.anchors.items()]
        return f"{self.label} ({', '.join(parts)})"


# --- anchor rules: the anchor year is computed from data, never typed ---------

# Series each rule reads to find the peak.
_RULE_SERIES = {
    "property_peak": "real_property_prices",
    "workingage_peak": "workingage_share",
}
_MIN_DECLINE_YEARS = 3  # property_peak: years of decline that confirm a real peak


@dataclass(frozen=True)
class AnchorResult:
    iso3: str
    rule: str
    year: int | None
    reason: str = ""  # why year is None (no data / no peak / not confirmed)


def anchor_year(iso3: str, rule: str, window: tuple[int, int]) -> AnchorResult:
    """Year `rule` selects for `iso3` inside `window` (inclusive), from the cache.

    `property_peak`: argmax of the real house-price index in the window, requiring
    at least `_MIN_DECLINE_YEARS` subsequent years all below the peak (so a rising
    market isn't mistaken for a bust). `workingage_peak`: argmax of the working-age
    share in the window. Returns `year=None` with a `reason` when the data can't
    support a call — the caller records the gap, it does not raise.
    """
    if rule not in _RULE_SERIES:
        raise KeyError(f"unknown anchor rule '{rule}'")
    key = _RULE_SERIES[rule]
    try:
        df = datastore.read(key)
    except FileNotFoundError:
        return AnchorResult(iso3, rule, None, f"no '{key}' cache")
    g = df[df["country"] == iso3].sort_values("year")
    if g.empty:
        return AnchorResult(iso3, rule, None, f"no '{key}' data for {iso3}")
    lo, hi = window
    w = g[g["year"].between(lo, hi)]
    if w.empty:
        return AnchorResult(iso3, rule, None, f"no '{key}' observation in {lo}-{hi}")
    peak = w.loc[w["value"].idxmax()]
    year = int(peak["year"])
    if rule == "property_peak":
        after = g[g["year"] > year].sort_values("year").head(_MIN_DECLINE_YEARS)
        if len(after) < _MIN_DECLINE_YEARS or bool(
            (after["value"] >= peak["value"]).any()
        ):
            return AnchorResult(
                iso3,
                rule,
                None,
                f"peak {year} not followed by {_MIN_DECLINE_YEARS} declining years",
            )
    return AnchorResult(iso3, rule, year)


def resolve_alignment(
    preset: str | None = None,
    anchor_overrides: dict | None = None,
) -> Alignment:
    """Build an Alignment. A named preset computes each country's anchor year with
    its rule (`property_peak` / `workingage_peak`) against that country's episode
    search window — no year is typed in. Explicit `anchor_overrides` win over the
    computed year (and are the only input when no preset is given).
    """
    anchors: dict[str, int] = {}
    rule = "explicit"
    if preset:
        if preset not in ANCHOR_PRESETS:
            raise KeyError(
                f"unknown anchor preset '{preset}'. choices: {sorted(ANCHOR_PRESETS)}"
            )
        p = ANCHOR_PRESETS[preset]
        rule = p.rule
        label = p.description
        for iso3 in COUNTRIES:
            res = anchor_year(iso3, p.rule, episode_window(iso3, p.set_name))
            if res.year is None:
                raise ValueError(
                    f"preset '{preset}': cannot anchor {iso3} — {res.reason}"
                )
            anchors[iso3] = res.year
    else:
        label = "custom anchors"
    if anchor_overrides:
        anchors.update({k.upper(): int(v) for k, v in anchor_overrides.items()})
        if preset:
            rule = "explicit"
    missing = set(COUNTRIES) - set(anchors)
    if missing:
        raise ValueError(f"no anchor year for: {sorted(missing)}")
    return Alignment(anchors=anchors, label=label, rule=rule)


def align_series(
    df: pd.DataFrame, alignment: Alignment, max_year: int = MAX_YEAR
) -> pd.DataFrame:
    """Add a `t` column = year - anchor[country]. Rows for unknown countries drop.

    Observations after `max_year` are dropped so IMF/BIS forward projections
    (e.g. WEO runs to +5y) and current-year partials don't get plotted as if
    they were realised data — the tool is about testing against *past* data.
    `MAX_YEAR` defaults to the last completed calendar year.
    """
    df = df[df["country"].isin(alignment.anchors) & (df["year"] <= max_year)].copy()
    if df.empty:
        return df.assign(t=pd.Series(dtype=int))
    df["t"] = df["year"].astype(int) - df["country"].map(alignment.anchors).astype(int)
    return df.sort_values(["country", "t"]).reset_index(drop=True)


def _anchor_base(g: pd.DataFrame, compare_as: str) -> float:
    """The value to normalise a country's series against: its observation at t=0,
    or the nearest available t (with a warning)."""
    base_row = g.iloc[(g["t"].abs()).argmin()]
    if base_row["t"] != 0:
        warnings.warn(
            f"{g['country'].iloc[0]}: no observation at the anchor year; "
            f"'{compare_as}' series based on t={int(base_row['t'])} instead",
            stacklevel=3,
        )
    return float(base_row["value"])


def apply_comparison_basis(df: pd.DataFrame, compare_as: str) -> pd.DataFrame:
    """Put an aligned frame onto the basis on which cross-country comparison is
    meaningful for its indicator (see `Series.compare_as`).

    - "level": returned unchanged.
    - "indexed_to_anchor": rescale each country so its value at t=0 (or the
      nearest t) is 100, cancelling any provider index base.
    - "slope": replace value with log(value / value_at_anchor) per country, so the
      series starts at 0 at t=0 and reads as cumulative log-change from the anchor.
      Only the trajectory then compares; the level gap at the anchor is recorded
      separately by the analyzer.
    """
    if compare_as not in ("indexed_to_anchor", "slope") or df.empty:
        return df
    out = df.copy()
    for country, g in df.groupby("country"):
        base = _anchor_base(g, compare_as)
        mask = out["country"] == country
        if compare_as == "indexed_to_anchor":
            if base:
                out.loc[mask, "value"] = out.loc[mask, "value"] / base * 100.0
        else:  # slope
            if base > 0:
                out.loc[mask, "value"] = np.log(out.loc[mask, "value"] / base)
    return out
