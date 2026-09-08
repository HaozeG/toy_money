import pandas as pd

from toy_money import datastore
from toy_money.config import SERIES


def test_normalize_dedupes_and_sorts():
    df = pd.DataFrame(
        {
            "country": ["chn", "CHN", "JPN"],
            "year": ["2020", 2020, 1990],
            "value": [1.0, 2.0, 3.0],
            "extra": [9, 9, 9],
        }
    )
    out = datastore.normalize(df)
    assert list(out.columns) == ["country", "year", "value"]
    assert len(out) == 2  # (CHN,2020) deduped, last wins
    assert out.iloc[0]["country"] == "CHN" and out.iloc[0]["year"] == 2020
    assert out.iloc[0]["value"] == 2.0


def test_normalize_drops_nulls():
    df = pd.DataFrame(
        {"country": ["JPN", "JPN"], "year": [1990, 1991], "value": [1.0, None]}
    )
    assert len(datastore.normalize(df)) == 1


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(datastore, "DATA_DIR", tmp_path)
    df = pd.DataFrame({"country": ["JPN"], "year": [1990], "value": [4.9]})
    datastore.write("demo", df)
    assert datastore.has("demo")
    back = datastore.read("demo")
    assert back.iloc[0]["value"] == 4.9


def test_provenance_tracks_write_and_seed_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(datastore, "DATA_DIR", tmp_path)
    df = pd.DataFrame({"country": ["JPN"], "year": [1990], "value": [4.9]})
    datastore.write("gdp_growth", df, provenance="seed")
    assert datastore.provenance("gdp_growth") == "seed"
    datastore.write("gdp_growth", df, provenance="live")
    assert datastore.provenance("gdp_growth") == "live"
    assert datastore.provenance("cpi_inflation") == "seed"  # uncached, seed exists
    assert datastore.provenance("no_such_key") == "missing"


def test_every_series_has_seed_data():
    for s in SERIES:
        assert datastore.seed_frame(s.key) is not None, f"no seed rows for {s.key}"
