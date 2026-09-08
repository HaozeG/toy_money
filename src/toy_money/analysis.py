"""Turn the aligned panels into stated conclusions.

The reference point is *China's latest observation* (`reference_t`): every finding
answers "given where China is now, what does the Japan precedent say?"

Design for reuse: an analyzer is any callable
`(panels, alignment) -> list[Finding]`. `path_overlap` is the first concrete one.
A second method (DTW, regime classifier, an LLM judge, ...) returns the same
`Finding` shape with its own `method` string, and the report renders it unchanged.

Deliberate non-features:
- No aggregate similarity score. Indicators have different units, different
  overlap lengths, and one is seed-sourced; averaging them produces a number
  that looks authoritative and means nothing. The headline is a *count*.
- No probability. n=1 precedent. Verdicts are categorical.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .align import Alignment, align_series, apply_comparison_basis
from .config import SERIES, Series
from . import datastore

# A verdict needs at least this many comparable (overlapping-t) years.
MIN_OVERLAP = 8
# "tracks" if China stays within this fraction of Japan's value at matched t
# (relative band for levels/indices; absolute pp for rates is handled below).
TRACK_REL_BAND = 0.20


@dataclass(frozen=True)
class PreparedPanel:
    series: Series
    df: pd.DataFrame  # columns: country, year, value, t  (comparison basis applied)
    provenance: str


@dataclass(frozen=True)
class Finding:
    key: str
    label: str
    method: str
    verdict: str  # tracks | diverges | indeterminate
    direction: str  # above | below | crossing | n/a  (China vs Japan at matched t)
    n_overlap: int
    reference_t: int  # China's latest t
    chn_at_ref: float | None
    jpn_at_ref: float | None  # Japan at the same t (the precedent value)
    jpn_forward: dict = field(default_factory=dict)  # {t: value} past reference_t
    provenance: str = "live"
    rationale: str = ""


def prepared_panels(
    alignment: Alignment, only_in_report: bool = True
) -> list[PreparedPanel]:
    """Aligned + comparison-basis-applied panels, shared by the report and analyzers."""
    out = []
    for s in SERIES:
        if only_in_report and not s.in_report:
            continue
        try:
            raw = datastore.read(s.key)
        except FileNotFoundError:
            continue
        df = apply_comparison_basis(align_series(raw, alignment), s.compare_as)
        if df.empty:
            continue
        out.append(PreparedPanel(s, df, datastore.provenance(s.key)))
    return out


def _series_by_country(df: pd.DataFrame, country: str) -> pd.Series:
    g = df[df["country"] == country].set_index("t")["value"].sort_index()
    return g[~g.index.duplicated(keep="last")]


def path_overlap(
    panels: list[PreparedPanel], alignment: Alignment
) -> list[Finding]:
    """Compare China's realised path to Japan's over the years both cover.

    verdict:
      indeterminate - fewer than MIN_OVERLAP overlapping years
      tracks        - median relative gap over the overlap window <= TRACK_REL_BAND
      diverges      - otherwise
    direction: where China sits relative to Japan at the reference point.
    """
    findings: list[Finding] = []
    for p in panels:
        chn = _series_by_country(p.df, "CHN")
        jpn = _series_by_country(p.df, "JPN")
        if chn.empty or jpn.empty:
            continue
        ref_t = int(chn.index.max())
        overlap = chn.index.intersection(jpn.index)
        n = len(overlap)

        chn_ref = float(chn.loc[ref_t]) if ref_t in chn.index else None
        jpn_ref = float(jpn.loc[ref_t]) if ref_t in jpn.index else None
        jpn_forward = {
            int(t): round(float(jpn.loc[t]), 2)
            for t in jpn.index
            if ref_t < t <= ref_t + 10
        }

        if n < MIN_OVERLAP:
            findings.append(
                Finding(
                    key=p.series.key, label=p.series.label, method="path_overlap",
                    verdict="indeterminate", direction="n/a", n_overlap=n,
                    reference_t=ref_t, chn_at_ref=chn_ref, jpn_at_ref=jpn_ref,
                    jpn_forward=jpn_forward, provenance=p.provenance,
                    rationale=f"only {n} overlapping years (need {MIN_OVERLAP})",
                )
            )
            continue

        c = chn.loc[overlap]
        j = jpn.loc[overlap]
        if p.series.compare_as == "slope":
            # Only the trajectory compares — re-base both to 100 at the first
            # shared year, so the test is "same shape", not "same level".
            c = c / c.iloc[0] * 100
            j = j / j.iloc[0] * 100
        scale = j.abs().clip(lower=1e-9)
        rel_gap = ((c - j).abs() / scale).median()
        verdict = "tracks" if rel_gap <= TRACK_REL_BAND else "diverges"

        if chn_ref is None or jpn_ref is None:
            direction = "n/a"
        elif abs(chn_ref - jpn_ref) / max(abs(jpn_ref), 1e-9) <= 0.03:
            direction = "crossing"
        else:
            direction = "above" if chn_ref > jpn_ref else "below"

        findings.append(
            Finding(
                key=p.series.key, label=p.series.label, method="path_overlap",
                verdict=verdict, direction=direction, n_overlap=n,
                reference_t=ref_t, chn_at_ref=chn_ref, jpn_at_ref=jpn_ref,
                jpn_forward=jpn_forward, provenance=p.provenance,
                rationale=f"median relative gap {rel_gap:.0%} over {n} years "
                f"(band {TRACK_REL_BAND:.0%})",
            )
        )
    return findings


ANALYZERS = {"path_overlap": path_overlap}


def headline(findings: list[Finding]) -> str:
    """A count, never an average."""
    tracks = sum(f.verdict == "tracks" for f in findings)
    total = sum(f.verdict != "indeterminate" for f in findings)
    indet = sum(f.verdict == "indeterminate" for f in findings)
    tail = f" ({indet} indeterminate)" if indet else ""
    return f"{tracks} of {total} indicators track Japan's path{tail}"
