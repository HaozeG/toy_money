import pandas as pd

from toy_money.align import Alignment
from toy_money.analysis import MIN_OVERLAP, PreparedPanel, headline, precedent
from toy_money.config import Series

_AL = Alignment(anchors={"JPN": 1990, "CHN": 2021}, label="test")


def _panel(key, rows, compare_as="level"):
    df = pd.DataFrame(rows, columns=["country", "year", "value"])
    df["t"] = df["year"] - df["country"].map(_AL.anchors)
    s = Series(key=key, label=key, unit="x", source="seed", compare_as=compare_as)
    return PreparedPanel(s, df, "live")


def _matched(cval, jval, n):
    rows = [("CHN", 2021 + i, cval) for i in range(-n + 1, 1)]
    rows += [("JPN", 1990 + i, jval) for i in range(-n + 1, 1)]
    return rows


def test_indeterminate_below_overlap_floor():
    (f,) = precedent([_panel("x", _matched(10, 10, MIN_OVERLAP - 1))], _AL)
    assert f.verdict == "indeterminate"
    assert f.direction == "n/a"
    assert f.n_overlap == MIN_OVERLAP - 1


def test_compared_reports_direction_not_similarity():
    (f,) = precedent([_panel("x", _matched(50.0, 100.0, 12))], _AL)
    assert f.verdict == "compared"  # never "tracks"/"diverges"
    assert f.direction == "below"  # China under Japan at the reference point


def test_direction_above_and_crossing():
    (hi,) = precedent([_panel("x", _matched(120.0, 100.0, 12))], _AL)
    assert hi.direction == "above"
    (mid,) = precedent([_panel("x", _matched(100.5, 100.0, 12))], _AL)
    assert mid.direction == "crossing"  # within 3%


def test_reference_point_is_china_latest_and_forward_is_japan_only():
    rows = _matched(10, 10, 10)
    rows += [("JPN", 1991 + i, 10) for i in range(10)]  # Japan runs past China
    (f,) = precedent([_panel("x", rows)], _AL)
    assert f.reference_t == 0  # China's last year 2021 -> t=0
    assert set(f.jpn_forward) == set(range(1, 11))


def test_headline_counts_directions_only():
    panels = [
        _panel("a", _matched(120.0, 100.0, 12)),  # above
        _panel("b", _matched(50.0, 100.0, 12)),  # below
        _panel("c", _matched(10, 10, 3)),  # indeterminate
    ]
    h = headline(precedent(panels, _AL))
    assert "1 and below on 1 of 2" in h
    assert "1 indeterminate" in h
    assert "track" not in h  # no similarity language
