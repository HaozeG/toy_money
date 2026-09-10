"""Aligned panels -> stated conclusions.

Reference point = China's latest observation (`reference_t`): every `Finding`
answers "given where China is now, what does the Japan precedent say?"

An analyzer is any `(panels, alignment) -> list[Finding]`; `precedent` is the
first. The report renders whatever `Finding`s it gets.

Non-features (see CLAUDE.md Working rules):
- No similarity score, no probability (n=1 precedent).
- No tracks/diverges verdict — any level-relative similarity band is scale-biased
  (working-age % on a ~67 base vs GDP growth % on a ~3 base). The finding carries
  the numbers; the reader judges.
- No headline scoreboard — a reader reads a tally as a verdict.
- Overlap counted only inside `ANALYSIS_WINDOW`, split pre/post anchor; the verdict
  gate is on `n_post` (the hypothesis is about the post-anchor path).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

import math

import numpy as np

from .align import Alignment, align_series, anchor_year, apply_comparison_basis
from .config import (
    ANALYSIS_WINDOW,
    EPISODES,
    HYPOTHESES,
    MAX_YEAR,
    SERIES,
    SERIES_BY_KEY,
    Series,
    episode_window,
)
from . import datastore

# Post-anchor overlapping years required before a direction is stated. The
# hypothesis is a claim about the post-anchor trajectory, so pre-anchor history
# does not count toward this gate.
#
# PLACEHOLDER: 3 is a floor for "can say anything at all". Phase B1 fixes the
# comparison window per sub-hypothesis and this should follow from that.
MIN_POST = 3


@dataclass(frozen=True)
class PreparedPanel:
    series: Series
    df: pd.DataFrame  # columns: country, year, value, t  (comparison basis applied)
    raw_df: pd.DataFrame  # same, aligned but PRE comparison-basis (native units)
    provenance: str


@dataclass(frozen=True)
class Finding:
    key: str
    label: str
    method: str
    compare_as: str  # level | indexed_to_anchor | slope  (how chn/jpn values read)
    verdict: str  # compared | indeterminate
    direction: str  # above | below | crossing | n/a  (China vs Japan at matched t)
    n_overlap: int  # n_pre + n_post, kept for compatibility
    n_pre: int  # overlapping t in window with t < 0
    n_post: int  # overlapping t in window with t >= 0
    reference_t: int  # China's latest t
    chn_at_ref: float | None
    jpn_at_ref: float | None  # Japan at the same t (the precedent value)
    jpn_forward: dict = field(default_factory=dict)  # {t: value} past reference_t
    # (chn, jpn) raw values at the anchor, native units — set for compare_as="slope"
    # where the level gap is a finding in its own right; None otherwise.
    level_gap_at_anchor: tuple[float, float] | None = None
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
        aligned = align_series(raw, alignment)
        df = apply_comparison_basis(aligned, s.compare_as)
        if df.empty:
            continue
        out.append(PreparedPanel(s, df, aligned, datastore.provenance(s.key)))
    return out


def _series_by_country(df: pd.DataFrame, country: str) -> pd.Series:
    g = df[df["country"] == country].set_index("t")["value"].sort_index()
    return g[~g.index.duplicated(keep="last")]


def _overlap_t(chn: pd.Series, jpn: pd.Series) -> pd.Index:
    """Common t values inside the shared analysis window."""
    common = chn.index.intersection(jpn.index)
    lo, hi = ANALYSIS_WINDOW
    return common[(common >= lo) & (common <= hi)]


def _direction(
    chn_ref: float | None, jpn_ref: float | None, band: float | None
) -> str:
    """Where China sits relative to Japan at the reference point.

    `band` is an absolute half-width in the indicator's natural unit; inside it
    the two are "crossing". `band is None` => only above/below.
    """
    if chn_ref is None or jpn_ref is None:
        return "n/a"
    if band is not None and abs(chn_ref - jpn_ref) <= band:
        return "crossing"
    return "above" if chn_ref > jpn_ref else "below"


def _level_gap_at_anchor(
    raw_df: pd.DataFrame,
) -> tuple[float, float] | None:
    """(China, Japan) raw values at (or nearest) t=0, in native units."""
    out = {}
    for c in ("CHN", "JPN"):
        g = raw_df[raw_df["country"] == c]
        if g.empty:
            return None
        out[c] = float(g.iloc[g["t"].abs().argmin()]["value"])
    return (out["CHN"], out["JPN"])


def precedent(panels: list[PreparedPanel], alignment: Alignment) -> list[Finding]:
    """For each indicator, read off the Japan precedent from China's current
    position: where China sits vs. Japan at the same t, and where Japan went next.

    Overlap is counted only inside `ANALYSIS_WINDOW` and split into pre/post
    anchor. The verdict gate is on post-anchor overlap (`n_post >= MIN_POST`),
    since the hypothesis is about the post-anchor path. No similarity verdict —
    see the module docstring. `verdict` is only `indeterminate` or `compared`.
    """
    findings: list[Finding] = []
    for p in panels:
        chn = _series_by_country(p.df, "CHN")
        jpn = _series_by_country(p.df, "JPN")
        if chn.empty or jpn.empty:
            continue
        ref_t = int(chn.index.max())
        overlap = _overlap_t(chn, jpn)
        n_pre = int((overlap < 0).sum())
        n_post = int((overlap >= 0).sum())
        chn_ref = float(chn.loc[ref_t]) if ref_t in chn.index else None
        jpn_ref = float(jpn.loc[ref_t]) if ref_t in jpn.index else None
        jpn_forward = {
            int(t): round(float(jpn.loc[t]), 4)
            for t in jpn.index
            if ref_t < t <= ref_t + 10
        }
        level_gap = (
            _level_gap_at_anchor(p.raw_df)
            if p.series.compare_as == "slope"
            else None
        )

        if n_post < MIN_POST:
            verdict, direction = "indeterminate", "n/a"
            rationale = (
                f"only {n_post} post-anchor overlapping year(s) "
                f"(need {MIN_POST}); {n_pre} pre-anchor"
            )
        elif jpn_ref is None:
            verdict, direction = "indeterminate", "n/a"
            rationale = (
                f"{n_post} post-anchor overlapping years, but no Japan "
                f"observation at China's reference t={ref_t}"
            )
        else:
            verdict = "compared"
            direction = _direction(chn_ref, jpn_ref, p.series.band)
            rationale = (
                f"{n_pre} pre-anchor, {n_post} post-anchor overlapping years "
                f"in t={ANALYSIS_WINDOW[0]}..{ANALYSIS_WINDOW[1]}"
            )

        findings.append(
            Finding(
                key=p.series.key,
                label=p.series.label,
                method="precedent",
                compare_as=p.series.compare_as,
                verdict=verdict,
                direction=direction,
                n_overlap=n_pre + n_post,
                n_pre=n_pre,
                n_post=n_post,
                reference_t=ref_t,
                chn_at_ref=chn_ref,
                jpn_at_ref=jpn_ref,
                jpn_forward=jpn_forward,
                level_gap_at_anchor=level_gap,
                provenance=p.provenance,
                rationale=rationale,
            )
        )
    return findings


ANALYZERS = {"precedent": precedent}


# --- episodes: China's Δ-from-anchor against a distribution of episodes --------


def _episode_trajectory(s: Series, iso3: str, anchor: int) -> dict[int, float] | str:
    """{t: comparison-basis value} for one country/series from t=0 onward, or a
    reason string if it can't be built.

    `compare_as="slope"` -> log(value / value_at_anchor). Otherwise
    `episode_basis` decides: "delta" -> Δ from the anchor value (level) or the
    re-indexed change (indexed_to_anchor); "level" -> the value itself (flow
    rates where the level is the point).
    """
    key = s.key
    try:
        raw = datastore.read(key)
    except FileNotFoundError:
        return f"no '{key}' cache"
    g = raw[(raw["country"] == iso3) & (raw["year"] <= MAX_YEAR)].copy()
    if g.empty:
        return f"no '{key}' data for {iso3}"
    g["t"] = g["year"].astype(int) - anchor
    at0 = g[g["t"] == 0]
    if at0.empty:
        return f"no '{key}' observation at the anchor year {anchor}"
    base = float(at0["value"].iloc[0])
    slope = s.compare_as == "slope"
    delta = s.episode_basis == "delta"
    out: dict[int, float] = {}
    for r in g.itertuples():
        t = int(r.t)
        if t < 0:
            continue
        v = float(r.value)
        if slope:
            if base <= 0 or v <= 0:
                return f"'{key}' non-positive value; log-change undefined"
            out[t] = math.log(v / base)
        elif not delta:
            out[t] = v
        elif s.compare_as == "indexed_to_anchor":
            if base == 0:
                return f"'{key}' anchor value is 0"
            out[t] = v / base * 100.0 - 100.0
        else:  # level, delta
            out[t] = v - base
    return out


@dataclass(frozen=True)
class EpisodeFinding:
    hypothesis: str
    key: str
    label: str
    unit: str
    compare_as: str
    basis: str  # "log-change" | "delta from anchor" | "level" — how values read
    horizon: int
    # t -> {"n", "min", "q1", "median", "q3", "max", "episodes": {iso3: value}}
    distribution: dict
    chn: dict  # t -> China's Δ (only where China has a post-anchor observation)
    chn_rank: dict  # t -> [k, n]  China is above k of n episode values
    jpn: dict  # t -> Japan's Δ (Japan is also in the distribution)
    unavailable: dict  # iso3 -> reason it is not in the distribution
    provenance: str = "live"


def episodes(panels: list[PreparedPanel], alignment: Alignment) -> list[EpisodeFinding]:
    """China's Δ-from-anchor at each post-anchor year, against the distribution of
    comparable episodes. Reads its own data per episode (each on its own computed
    anchor) — `panels`/`alignment` are unused. No similarity verdict, no rank in
    any headline: the Finding carries the numbers.
    """
    findings: list[EpisodeFinding] = []
    for h in HYPOTHESES:
        eps = [e for e in EPISODES if e.set_name == h.set_name]
        # Resolve each episode's anchor once.
        anchors: dict[str, int] = {}
        anchor_gap: dict[str, str] = {}
        for e in eps:
            res = anchor_year(e.iso3, e.anchor_rule, e.search_window)
            if res.year is None:
                anchor_gap[e.iso3] = res.reason
            else:
                anchors[e.iso3] = res.year

        for key in h.series:
            s = SERIES_BY_KEY[key]
            deltas: dict[str, dict[int, float]] = {}
            unavailable = dict(anchor_gap)
            for iso3, a in anchors.items():
                d = _episode_trajectory(s, iso3, a)
                if isinstance(d, str):
                    unavailable[iso3] = d
                else:
                    deltas[iso3] = d

            dist: dict[int, dict] = {}
            chn: dict[int, float] = {}
            chn_rank: dict[int, list] = {}
            jpn: dict[int, float] = {}
            for t in range(0, h.horizon + 1):
                # Distribution = every episode with an observation at t, China
                # included as the subject but reported separately.
                others = {
                    iso3: dd[t]
                    for iso3, dd in deltas.items()
                    if iso3 != "CHN" and t in dd
                }
                if len(others) >= 3:
                    vals = np.array(sorted(others.values()), dtype=float)
                    dist[t] = {
                        "n": int(len(vals)),
                        "min": float(vals.min()),
                        "q1": float(np.percentile(vals, 25)),
                        "median": float(np.median(vals)),
                        "q3": float(np.percentile(vals, 75)),
                        "max": float(vals.max()),
                        "episodes": {k: round(v, 4) for k, v in others.items()},
                    }
                    if "JPN" in others:
                        jpn[t] = round(others["JPN"], 4)
                    cd = deltas.get("CHN", {})
                    if t in cd:
                        chn[t] = round(cd[t], 4)
                        chn_rank[t] = [int((vals < cd[t]).sum()), int(len(vals))]
            findings.append(
                EpisodeFinding(
                    hypothesis=h.name,
                    key=key,
                    label=s.label,
                    unit=s.unit,
                    compare_as=s.compare_as,
                    basis=(
                        "log-change"
                        if s.compare_as == "slope"
                        else "level"
                        if s.episode_basis == "level"
                        else "delta from anchor"
                    ),
                    horizon=h.horizon,
                    distribution=dist,
                    chn=chn,
                    chn_rank=chn_rank,
                    jpn=jpn,
                    unavailable=unavailable,
                    provenance=datastore.provenance(key),
                )
            )
    return findings


ANALYZERS["episodes"] = episodes


def headline(findings: list[Finding]) -> str:
    """Names the scope of the comparison. No direction tally — a reader takes a
    count as a verdict, and the per-indicator table already carries the directions.
    """
    n = len(findings)
    compared = sum(f.verdict == "compared" for f in findings)
    indet = n - compared
    if indet:
        return (
            f"{n} indicators; {compared} have a China-vs-Japan direction at "
            f"China's reference point, {indet} indeterminate. Table and chart below"
        )
    return (
        f"{n} indicators, each with a China-vs-Japan direction at China's "
        f"reference point. Table and chart below"
    )
