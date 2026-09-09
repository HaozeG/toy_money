import math

import pandas as pd

from toy_money.align import Alignment, apply_comparison_basis
from toy_money.analysis import MIN_POST, PreparedPanel, headline, precedent
from toy_money.config import Series

_AL = Alignment(anchors={"JPN": 1990, "CHN": 2021}, label="test")


def _panel(key, chn, jpn, *, compare_as="level", band=None):
    """chn / jpn: {t: value}. Builds a PreparedPanel with raw_df (pre-basis) and
    df (post comparison-basis)."""
    rows = [("CHN", 2021 + t, v, t) for t, v in chn.items()]
    rows += [("JPN", 1990 + t, v, t) for t, v in jpn.items()]
    raw = pd.DataFrame(rows, columns=["country", "year", "value", "t"])
    df = apply_comparison_basis(raw, compare_as)
    s = Series(
        key=key, label=key, unit="x", source="seed", compare_as=compare_as, band=band
    )
    return PreparedPanel(s, df, raw, "live")


def _flat(t_lo, t_hi, v):
    return {t: float(v) for t in range(t_lo, t_hi + 1)}


def test_indeterminate_when_too_few_post_anchor_years():
    # overlap t=-10..1 -> n_post = 2 < MIN_POST
    (f,) = precedent([_panel("x", _flat(-10, 1, 10), _flat(-10, 1, 10))], _AL)
    assert f.verdict == "indeterminate"
    assert f.direction == "n/a"
    assert f.n_post == 2 and f.n_post < MIN_POST


def test_pre_anchor_years_do_not_rescue_the_verdict():
    # 20 pre-anchor overlapping years, still only 2 post -> indeterminate
    (f,) = precedent([_panel("x", _flat(-20, 1, 10), _flat(-20, 1, 10))], _AL)
    assert f.n_pre == 20 and f.n_post == 2
    assert f.verdict == "indeterminate"


def test_compared_when_enough_post_anchor_years():
    (f,) = precedent([_panel("x", _flat(-5, 5, 50.0), _flat(-5, 5, 100.0))], _AL)
    assert f.verdict == "compared"
    assert f.n_post == 6
    assert f.n_overlap == f.n_pre + f.n_post


def test_direction_is_above_below_on_raw_sign_when_band_none():
    (hi,) = precedent([_panel("x", _flat(-5, 5, 120.0), _flat(-5, 5, 100.0))], _AL)
    assert hi.direction == "above"
    (lo,) = precedent([_panel("x", _flat(-5, 5, 80.0), _flat(-5, 5, 100.0))], _AL)
    assert lo.direction == "below"


def test_crossing_requires_an_absolute_band():
    chn, jpn = _flat(-5, 5, 100.5), _flat(-5, 5, 100.0)
    (no_band,) = precedent([_panel("x", chn, jpn, band=None)], _AL)
    assert no_band.direction == "above"  # 0.5 apart, but no band -> sign only
    (with_band,) = precedent([_panel("x", chn, jpn, band=1.0)], _AL)
    assert with_band.direction == "crossing"


def test_reference_point_is_china_latest_and_forward_is_japan_only():
    chn = _flat(-3, 3, 10.0)
    jpn = _flat(-3, 13, 10.0)  # Japan runs well past China
    (f,) = precedent([_panel("x", chn, jpn)], _AL)
    assert f.reference_t == 3
    assert set(f.jpn_forward) == set(range(4, 14))


def test_missing_japan_reference_is_indeterminate():
    chn = _flat(-5, 3, 10.0)
    jpn = _flat(-5, 2, 10.0)  # no Japan obs at China's reference t=3
    (f,) = precedent([_panel("x", chn, jpn)], _AL)
    assert f.n_post == 3  # t=0,1,2 overlap
    assert f.verdict == "indeterminate"
    assert "no Japan observation" in f.rationale


def test_overlap_counts_only_analysis_window():
    (f,) = precedent([_panel("x", _flat(-30, 3, 1.0), _flat(-30, 3, 1.0))], _AL)
    assert f.n_pre == 25  # t=-25..-1, not -30..-1
    assert f.n_post == 4  # t=0..3
    assert "-25..35" in f.rationale


def test_slope_transform_compares_shape_and_records_level_gap():
    chn = {0: 100.0, 3: 200.0, 5: 300.0}
    jpn = {0: 1000.0, 3: 1200.0, 5: 1400.0}
    (f,) = precedent([_panel("g", chn, jpn, compare_as="slope")], _AL)
    assert f.level_gap_at_anchor == (100.0, 1000.0)
    # China's cumulative log-growth to t=5 (log 3) exceeds Japan's (log 1.4)
    assert f.chn_at_ref == math.log(3.0)
    assert f.direction == "above"


def test_headline_has_no_direction_scoreboard():
    panels = [
        _panel("a", _flat(-5, 5, 120.0), _flat(-5, 5, 100.0)),  # above
        _panel("b", _flat(-5, 5, 80.0), _flat(-5, 5, 100.0)),  # below
        _panel("c", _flat(-10, 1, 10.0), _flat(-10, 1, 10.0)),  # indeterminate
    ]
    h = headline(precedent(panels, _AL))
    assert "3 indicators" in h
    assert "1 indeterminate" in h
    for banned in ("above", "below on", "crossing", "track"):
        assert banned not in h
