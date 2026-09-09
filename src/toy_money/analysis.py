"""Turn the aligned panels into stated conclusions.

The reference point is *China's latest observation* (`reference_t`): every finding
answers "given where China is now, what does the Japan precedent say?"

Design for reuse: an analyzer is any callable
`(panels, alignment) -> list[Finding]`. `precedent` is the first concrete one.
A second method (DTW, regime classifier, an LLM judge, ...) returns the same
`Finding` shape with its own `method` string, and the report renders it unchanged.

Deliberate non-features:
- No aggregate similarity score. Indicators have different units, different
  overlap lengths, and mixed provenance; averaging them produces a number that
  looks authoritative and means nothing.
- No probability. n=1 precedent (Japan only).
- **No automatic "tracks vs. diverges" verdict.** That binary needs a defensible
  similarity band, and any level-relative band is scale-biased: an indicator on a
  ~67 base (working-age %) and one on a ~3 base (GDP growth %) with the *same*
  shape agreement get opposite verdicts purely from the denominator. Two attempts
  at a scale-free normalisation both failed on flat-Japan windows. So a finding
  carries the numbers — where China sits relative to Japan at matched t, and
  Japan's subsequent path — and the reader judges similarity. The headline counts
  *directions*, which is arithmetic.
- Overlap is counted only inside `ANALYSIS_WINDOW`, so the comparison does not
  silently span China's pre-reform years and Japan's 1960s.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .align import Alignment, align_series, apply_comparison_basis
from .config import ANALYSIS_WINDOW, SERIES, Series
from . import datastore

# Below this many overlapping-t years there is not enough comparable history to
# say anything — the finding is `indeterminate`.
MIN_OVERLAP = 8


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
    verdict: str  # compared | indeterminate
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


def _overlap_t(chn: pd.Series, jpn: pd.Series) -> pd.Index:
    """Common t values inside the shared analysis window."""
    common = chn.index.intersection(jpn.index)
    lo, hi = ANALYSIS_WINDOW
    return common[(common >= lo) & (common <= hi)]


def _direction(chn_ref: float | None, jpn_ref: float | None) -> str:
    """Where China sits relative to Japan at the reference point."""
    if chn_ref is None or jpn_ref is None:
        return "n/a"
    if abs(chn_ref - jpn_ref) / max(abs(jpn_ref), 1e-9) <= 0.03:
        return "crossing"
    return "above" if chn_ref > jpn_ref else "below"


def precedent(panels: list[PreparedPanel], alignment: Alignment) -> list[Finding]:
    """For each indicator, read off the Japan precedent from China's current
    position: where China sits vs. Japan at the same t, and where Japan went next.

    Overlap is counted only inside `ANALYSIS_WINDOW`, so the count reflects the
    shared, economically comparable part of the two timelines rather than the
    whole intersection. No similarity verdict — see the module docstring.
    `verdict` is only `indeterminate` or `compared`.
    """
    findings: list[Finding] = []
    for p in panels:
        chn = _series_by_country(p.df, "CHN")
        jpn = _series_by_country(p.df, "JPN")
        if chn.empty or jpn.empty:
            continue
        ref_t = int(chn.index.max())
        n = len(_overlap_t(chn, jpn))
        chn_ref = float(chn.loc[ref_t]) if ref_t in chn.index else None
        jpn_ref = float(jpn.loc[ref_t]) if ref_t in jpn.index else None
        jpn_forward = {
            int(t): round(float(jpn.loc[t]), 2)
            for t in jpn.index
            if ref_t < t <= ref_t + 10
        }
        if n < MIN_OVERLAP:
            verdict = "indeterminate"
            direction = "n/a"
            rationale = (
                f"only {n} overlapping years in t={ANALYSIS_WINDOW[0]}.."
                f"{ANALYSIS_WINDOW[1]} (need {MIN_OVERLAP})"
            )
        elif jpn_ref is None:
            # There is enough overlap, but Japan has no observation at the
            # exact reference t, so no matched-t direction can be stated.
            verdict = "indeterminate"
            direction = "n/a"
            rationale = (
                f"{n} overlapping years, but no Japan observation at China's "
                f"reference t={ref_t}"
            )
        else:
            verdict = "compared"
            direction = _direction(chn_ref, jpn_ref)
            rationale = (
                f"{n} overlapping years in t={ANALYSIS_WINDOW[0]}.."
                f"{ANALYSIS_WINDOW[1]}"
            )
        findings.append(
            Finding(
                key=p.series.key,
                label=p.series.label,
                method="precedent",
                verdict=verdict,
                direction=direction,
                n_overlap=n,
                reference_t=ref_t,
                chn_at_ref=chn_ref,
                jpn_at_ref=jpn_ref,
                jpn_forward=jpn_forward,
                provenance=p.provenance,
                rationale=rationale,
            )
        )
    return findings


ANALYZERS = {"precedent": precedent}


def headline(findings: list[Finding]) -> str:
    """Descriptive counts only — directions are arithmetic; similarity is not."""
    compared = [f for f in findings if f.verdict == "compared"]
    indet = len(findings) - len(compared)
    above = sum(f.direction == "above" for f in compared)
    below = sum(f.direction == "below" for f in compared)
    crossing = sum(f.direction == "crossing" for f in compared)
    if indet:
        lead = (
            f"{len(findings)} indicators: {len(compared)} comparable, "
            f"{indet} indeterminate"
        )
    else:
        lead = f"{len(findings)} indicators compared"
    return (
        f"{lead}; at matched t China is above Japan on {above}, below on {below}, "
        f"and crossing on {crossing} of {len(compared)}"
    )
