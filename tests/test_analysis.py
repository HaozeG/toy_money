import pandas as pd

from toy_money.align import Alignment
from toy_money.analysis import (
    MIN_OVERLAP,
    PreparedPanel,
    headline,
    path_overlap,
)
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
    p = _panel("x", _matched(10, 10, MIN_OVERLAP - 1))
    (f,) = path_overlap([p], _AL)
    assert f.verdict == "indeterminate"
    assert f.n_overlap == MIN_OVERLAP - 1


def test_tracks_when_paths_close():
    p = _panel("x", _matched(100.0, 105.0, 12))  # 5% gap < 20% band
    (f,) = path_overlap([p], _AL)
    assert f.verdict == "tracks"


def test_diverges_when_paths_far():
    p = _panel("x", _matched(50.0, 100.0, 12))  # 50% gap
    (f,) = path_overlap([p], _AL)
    assert f.verdict == "diverges"
    assert f.direction == "below"  # China under Japan at the reference point


def test_reference_point_is_china_latest():
    rows = _matched(10, 10, 10)
    rows += [("JPN", 1991 + i, 10) for i in range(10)]  # Japan runs past China
    p = _panel("x", rows)
    (f,) = path_overlap([p], _AL)
    assert f.reference_t == 0  # China's last year is 2021 -> t=0
    assert set(f.jpn_forward) == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}


def test_slope_series_compares_shape_not_level():
    # China a tenth of Japan's level but identical growth -> should track.
    rows = [("CHN", 2012 + i, 100 * 1.05**i) for i in range(10)]
    rows += [("JPN", 1981 + i, 1000 * 1.05**i) for i in range(10)]
    p = _panel("gdp", rows, compare_as="slope")
    (f,) = path_overlap([p], _AL)
    assert f.verdict == "tracks"
    assert f.direction == "below"


def test_headline_is_a_count_not_an_average():
    p_track = _panel("a", _matched(100.0, 105.0, 12))
    p_div = _panel("b", _matched(50.0, 100.0, 12))
    p_indet = _panel("c", _matched(10, 10, 3))
    assert headline(path_overlap([p_track, p_div, p_indet], _AL)) == (
        "1 of 2 indicators track Japan's path (1 indeterminate)"
    )
