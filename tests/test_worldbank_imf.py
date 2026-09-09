import pytest

from toy_money.config import Series
from toy_money.sources import imf, worldbank


def test_worldbank_fetch_parses_payload(monkeypatch):
    payload = [
        {"page": 1},
        [
            {"countryiso3code": "CHN", "date": "2020", "value": 1.0},
            {"countryiso3code": "JPN", "date": "2020", "value": 2.0},
        ],
    ]
    monkeypatch.setattr(worldbank, "get_json", lambda url, params: payload)

    out = worldbank.fetch(
        Series(key="x", label="x", unit="%", source="worldbank", params={"indicator": "X"})
    )
    got = {(r.country, r.year): r.value for r in out.itertuples()}
    assert got == {("CHN", "2020"): 1.0, ("JPN", "2020"): 2.0}


def test_worldbank_rejects_empty_payload(monkeypatch):
    monkeypatch.setattr(worldbank, "get_json", lambda url, params: [{"page": 1}, None])

    with pytest.raises(RuntimeError, match="no data"):
        worldbank.fetch(
            Series(
                key="x", label="x", unit="%", source="worldbank", params={"indicator": "X"}
            )
        )


def test_imf_fetch_parses_payload(monkeypatch):
    payload = {
        "values": {
            "X": {
                "CHN": {"2020": 1.0, "2021": 1.1},
                "JPN": {"2020": 2.0, "2021": 2.1},
            }
        }
    }
    monkeypatch.setattr(imf, "get_json", lambda url: payload)

    out = imf.fetch(
        Series(key="x", label="x", unit="%", source="imf", params={"indicator": "X"})
    )
    got = {(r.country, r.year): r.value for r in out.itertuples()}
    assert got[("CHN", "2020")] == 1.0
    assert got[("JPN", "2021")] == 2.1
