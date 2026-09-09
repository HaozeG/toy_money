import pandas as pd
import pytest

from toy_money.align import align_series, resolve_alignment
from toy_money.config import MAX_YEAR


def test_preset_resolves():
    a = resolve_alignment("bubble_peak")
    assert a.anchors == {"JPN": 1990, "CHN": 2021}


def test_override_beats_preset():
    a = resolve_alignment("bubble_peak", {"CHN": 2020})
    assert a.anchors["CHN"] == 2020
    assert a.anchors["JPN"] == 1990


def test_custom_without_all_countries_raises():
    with pytest.raises(ValueError):
        resolve_alignment(None, {"JPN": 1990})


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        resolve_alignment("nope")


def test_align_drops_projection_years():
    df = pd.DataFrame(
        {
            "country": ["JPN", "JPN", "CHN", "CHN"],
            "year": [1990, 2031, 2021, 2031],
            "value": [1.0, 2.0, 3.0, 4.0],
        }
    )
    out = align_series(df, resolve_alignment("bubble_peak"), max_year=2026)
    assert set(out["year"]) == {1990, 2021}


def test_align_drops_current_year_forecasts_by_default():
    df = pd.DataFrame(
        {
            "country": ["CHN", "CHN"],
            "year": [MAX_YEAR, MAX_YEAR + 1],
            "value": [1.0, 2.0],
        }
    )
    out = align_series(df, resolve_alignment("bubble_peak"))
    assert set(out["year"]) == {MAX_YEAR}


def test_align_shifts_to_years_since_anchor():
    df = pd.DataFrame(
        {
            "country": ["JPN", "JPN", "CHN", "CHN"],
            "year": [1989, 1990, 2021, 2022],
            "value": [1.0, 2.0, 3.0, 4.0],
        }
    )
    out = align_series(df, resolve_alignment("bubble_peak"))
    got = {(r.country, r.t): r.value for r in out.itertuples()}
    assert got[("JPN", -1)] == 1.0
    assert got[("JPN", 0)] == 2.0
    assert got[("CHN", 0)] == 3.0
    assert got[("CHN", 1)] == 4.0
