import math

import pandas as pd
import pytest

from toy_money import analysis
from toy_money.align import AnchorResult
from toy_money.config import Episode, Hypothesis, Series


def _frame(rows):
    return pd.DataFrame(rows, columns=["country", "year", "value"])


def test_trajectory_delta_from_anchor_for_a_level_series(monkeypatch):
    s = Series(key="k", label="k", unit="%", source="seed")  # episode_basis="delta"
    df = _frame([("JPN", 1990, 50.0), ("JPN", 1991, 55.0), ("JPN", 1992, 48.0)])
    monkeypatch.setattr(analysis.datastore, "read", lambda key: df)
    assert analysis._episode_trajectory(s, "JPN", 1990) == {0: 0.0, 1: 5.0, 2: -2.0}


def test_trajectory_level_basis_keeps_the_value():
    s = Series(key="k", label="k", unit="%", source="seed", episode_basis="level")
    df = _frame([("JPN", 1990, 3.0), ("JPN", 1991, 1.0)])
    m = pytest.MonkeyPatch()
    m.setattr(analysis.datastore, "read", lambda key: df)
    try:
        assert analysis._episode_trajectory(s, "JPN", 1990) == {0: 3.0, 1: 1.0}
    finally:
        m.undo()


def test_trajectory_slope_is_log_change():
    s = Series(key="k", label="k", unit="x", source="seed", compare_as="slope")
    df = _frame([("X", 2000, 100.0), ("X", 2001, 110.0)])
    m = pytest.MonkeyPatch()
    m.setattr(analysis.datastore, "read", lambda key: df)
    try:
        traj = analysis._episode_trajectory(s, "X", 2000)
    finally:
        m.undo()
    assert traj[0] == 0.0
    assert traj[1] == pytest.approx(math.log(1.1))


def test_trajectory_reports_reason_when_no_anchor_observation():
    s = Series(key="k", label="k", unit="%", source="seed")
    df = _frame([("X", 2005, 10.0)])
    m = pytest.MonkeyPatch()
    m.setattr(analysis.datastore, "read", lambda key: df)
    try:
        r = analysis._episode_trajectory(s, "X", 2000)
    finally:
        m.undo()
    assert isinstance(r, str) and "anchor year 2000" in r


def test_episodes_distribution_rank_and_unavailable(monkeypatch):
    # Five episodes; DEU has no data at its anchor -> unavailable. At t=1 the
    # deltas are CHN +5, JPN 0, FIN +10, SWE +2, so the distribution
    # (JPN, FIN, SWE) is [0, 2, 10] and China is above 2 of 3.
    hyp = Hypothesis("h", "set", ("k",), 3, "H")
    eps = [
        Episode("CHN", "property_peak", (2019, 2024), "China", "set"),
        Episode("JPN", "property_peak", (1988, 1994), "Japan", "set"),
        Episode("FIN", "property_peak", (1987, 1993), "Finland", "set"),
        Episode("SWE", "property_peak", (1987, 1993), "Sweden", "set"),
        Episode("DEU", "property_peak", (1980, 1990), "Germany", "set"),
    ]
    anchors = {"CHN": 2021, "JPN": 1991, "FIN": 1989, "SWE": 1990, "DEU": 1985}
    data = {
        "CHN": _frame([("CHN", 2021, 100.0), ("CHN", 2022, 105.0)]),
        "JPN": _frame([("JPN", 1991, 200.0), ("JPN", 1992, 200.0)]),
        "FIN": _frame([("FIN", 1989, 50.0), ("FIN", 1990, 60.0)]),
        "SWE": _frame([("SWE", 1990, 50.0), ("SWE", 1991, 52.0)]),
        "DEU": _frame([("DEU", 1990, 10.0)]),  # nothing at 1985
    }

    monkeypatch.setattr(analysis, "HYPOTHESES", [hyp])
    monkeypatch.setattr(analysis, "EPISODES", eps)
    monkeypatch.setattr(
        analysis,
        "SERIES_BY_KEY",
        {"k": Series(key="k", label="K", unit="%", source="seed")},
    )
    monkeypatch.setattr(
        analysis,
        "anchor_year",
        lambda iso3, rule, window: AnchorResult(
            iso3, rule, anchors.get(iso3), "" if iso3 in anchors else "no data"
        ),
    )
    # read(key) returns all countries for a series; the trajectory fn filters.
    allrows = pd.concat(data.values(), ignore_index=True)
    monkeypatch.setattr(analysis.datastore, "read", lambda key: allrows)
    monkeypatch.setattr(analysis.datastore, "provenance", lambda key: "live")

    (f,) = analysis.episodes([], None)
    assert f.hypothesis == "h" and f.key == "k"
    assert f.unavailable["DEU"].startswith("no '") or "1985" in f.unavailable["DEU"]
    d1 = f.distribution[1]
    assert d1["n"] == 3
    assert d1["min"] == 0.0 and d1["max"] == 10.0 and d1["median"] == 2.0
    assert f.jpn[1] == 0.0
    assert f.chn[1] == 5.0
    assert f.chn_rank[1] == [2, 3]  # above 2 of 3
