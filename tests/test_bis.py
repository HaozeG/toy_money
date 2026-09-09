import pytest

from toy_money.config import Series
from toy_money.sources import bis


def _series(**params):
    return Series(key="test", label="test", unit="%", source="bis", params=params)


def _fake_text(csv_by_cty):
    def fake(url, params):
        cty = "CN" if ".CN." in url else "JP"
        return csv_by_cty[cty]

    return fake


def test_bis_tc_validates_and_annualises(monkeypatch):
    csv_by_cty = {
        "CN": (
            "FREQ,BORROWERS_CTY,TC_BORROWERS,TC_LENDERS,VALUATION,UNIT_TYPE,"
            "TIME_PERIOD,OBS_VALUE\n"
            "Q,CN,H,A,M,770,2020-Q1,50\n"
            "Q,CN,H,A,M,770,2020-Q2,52\n"
        ),
        "JP": (
            "FREQ,BORROWERS_CTY,TC_BORROWERS,TC_LENDERS,VALUATION,UNIT_TYPE,"
            "TIME_PERIOD,OBS_VALUE\n"
            "Q,JP,H,A,M,770,2020-Q1,70\n"
            "Q,JP,H,A,M,770,2020-Q2,72\n"
        ),
    }
    monkeypatch.setattr(bis, "get_text", _fake_text(csv_by_cty))

    out = bis.fetch(_series(borrowers="H"))
    got = {(r.country, r.year): r.value for r in out.itertuples()}
    assert got[("CHN", 2020)] == 51.0
    assert got[("JPN", 2020)] == 71.0


def test_bis_property_validates_and_annualises(monkeypatch):
    csv_by_cty = {
        "CN": (
            "FREQ,REF_AREA,VALUE,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
            "Q,CN,R,628,2020-Q1,100\n"
            "Q,CN,R,628,2020-Q2,104\n"
        ),
        "JP": (
            "FREQ,REF_AREA,VALUE,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"
            "Q,JP,R,628,2020-Q1,90\n"
            "Q,JP,R,628,2020-Q2,94\n"
        ),
    }
    monkeypatch.setattr(bis, "get_text", _fake_text(csv_by_cty))

    out = bis.fetch(_series(dataset="WS_SPP"))
    got = {(r.country, r.year): r.value for r in out.itertuples()}
    assert got[("CHN", 2020)] == 102.0
    assert got[("JPN", 2020)] == 92.0


def test_bis_rejects_wrong_dimension_values(monkeypatch):
    csv = (
        "FREQ,BORROWERS_CTY,TC_BORROWERS,TC_LENDERS,VALUATION,UNIT_TYPE,"
        "TIME_PERIOD,OBS_VALUE\n"
        "Q,CN,P,A,M,770,2020-Q1,50\n"
    )
    monkeypatch.setattr(
        bis, "get_text", _fake_text({"CN": csv, "JP": csv.replace("CN", "JP")})
    )

    with pytest.raises(RuntimeError, match="did not resolve to the intended series"):
        bis.fetch(_series(borrowers="H"))


def test_bis_rejects_csv_without_dimension_columns(monkeypatch):
    csv = "TIME_PERIOD,OBS_VALUE\n2020-Q1,50\n"
    monkeypatch.setattr(bis, "get_text", _fake_text({"CN": csv, "JP": csv}))

    with pytest.raises(RuntimeError, match="missing expected dimension columns"):
        bis.fetch(_series(borrowers="H"))
