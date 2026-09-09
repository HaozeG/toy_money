"""Anchor logic: re-express each country's series on a shared
"years since anchor" axis so Japan and China curves overlay directly.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import pandas as pd

from .config import ANCHOR_PRESETS, COUNTRIES, MAX_YEAR


@dataclass(frozen=True)
class Alignment:
    anchors: dict  # ISO3 -> anchor year
    label: str

    def describe(self) -> str:
        parts = [f"{COUNTRIES.get(k, k)} {v}" for k, v in self.anchors.items()]
        return f"{self.label} ({', '.join(parts)})"


def resolve_alignment(
    preset: str | None = None,
    anchor_overrides: dict | None = None,
) -> Alignment:
    """Build an Alignment from a named preset and/or explicit per-country years."""
    if preset:
        if preset not in ANCHOR_PRESETS:
            raise KeyError(
                f"unknown anchor preset '{preset}'. "
                f"choices: {sorted(ANCHOR_PRESETS)}"
            )
        p = ANCHOR_PRESETS[preset]
        anchors = dict(p.anchors)
        label = p.description
    else:
        anchors = {}
        label = "custom anchors"
    if anchor_overrides:
        anchors.update({k.upper(): int(v) for k, v in anchor_overrides.items()})
    missing = set(COUNTRIES) - set(anchors)
    if missing:
        raise ValueError(f"no anchor year for: {sorted(missing)}")
    return Alignment(anchors=anchors, label=label)


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


def apply_comparison_basis(df: pd.DataFrame, compare_as: str) -> pd.DataFrame:
    """Put an aligned frame onto the basis on which cross-country comparison is
    meaningful for its indicator (see `Series.compare_as`).

    - "level" / "slope": returned unchanged (slope handling is the caller's job).
    - "indexed_to_anchor": rescale each country so its value at t=0 — or the
      observation nearest t=0 — is 100, cancelling any provider index base.
    """
    if compare_as != "indexed_to_anchor" or df.empty:
        return df
    out = df.copy()
    for country, g in df.groupby("country"):
        base_row = g.iloc[(g["t"].abs()).argmin()]
        base = base_row["value"]
        if base_row["t"] != 0:
            warnings.warn(
                f"{country}: no observation at the anchor year; re-indexing "
                f"'indexed_to_anchor' series to t={int(base_row['t'])} instead",
                stacklevel=2,
            )
        if base:
            out.loc[out["country"] == country, "value"] = (
                out.loc[out["country"] == country, "value"] / base * 100.0
            )
    return out
