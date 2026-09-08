"""Anchor logic: re-express each country's series on a shared
"years since anchor" axis so Japan and China curves overlay directly.
"""

from __future__ import annotations

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
    (e.g. WEO runs to +5y) don't get plotted as if they were realised data —
    the tool is about testing against *past* data.
    """
    df = df[df["country"].isin(alignment.anchors) & (df["year"] <= max_year)].copy()
    if df.empty:
        return df.assign(t=pd.Series(dtype=int))
    df["t"] = df["year"].astype(int) - df["country"].map(alignment.anchors).astype(int)
    return df.sort_values(["country", "t"]).reset_index(drop=True)
