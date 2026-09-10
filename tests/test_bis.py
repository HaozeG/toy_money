import pytest

from toy_money.config import Series
from toy_money.sources import bis

_TC_COLS = (
    "FREQ,BORROWERS_CTY,TC_BORROWERS,TC_LENDERS,VALUATION,UNIT_TYPE,"
    "TIME_PERIOD,OBS_VALUE\n"
)
_SPP_COLS = "FREQ,REF_AREA,VALUE,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n"


def _series(**params):
    return Series(key="test", label="test", unit="%", source="bis", params=params)


def _iso2_in_url(url: str) -> str:
    # key layout: .../{flow}/Q.{CTY}.{...}/all — the ISO2 is the 2nd key segment
    key = url.split("/all")[0].rsplit("/", 1)[1]
    return key.split(".")[1]


def _tc_provider(available, borrowers="H", value=50):
    """Fake get_text: returns a valid TC CSV for `available` ISO2s, 404s the rest."""

    def fake(url, params):
        cty = _iso2_in_url(url)
        if cty not in available:
            raise RuntimeError(f"HTTP 404 for {cty}")
        return _TC_COLS + (
            f"Q,{cty},{borrowers},A,M,770,2020-Q1,{value}\n"
            f"Q,{cty},{borrowers},A,M,770,2020-Q2,{value + 2}\n"
        )

    return fake


def test_bis_tc_validates_and_annualises(monkeypatch):
    monkeypatch.setattr(bis, "get_text", _tc_provider({"CN", "JP"}, value=50))
    out = bis.fetch(_series(borrowers="H"))
    got = {(r.country, r.year): r.value for r in out.itertuples()}
    assert got[("CHN", 2020)] == 51.0
    assert got[("JPN", 2020)] == 51.0


def test_bis_property_validates_and_annualises(monkeypatch):
    def fake(url, params):
        cty = _iso2_in_url(url)
        if cty not in {"CN", "JP"}:
            raise RuntimeError(f"HTTP 404 for {cty}")
        base = 100 if cty == "CN" else 90
        return _SPP_COLS + (
            f"Q,{cty},R,628,2020-Q1,{base}\n"
            f"Q,{cty},R,628,2020-Q2,{base + 4}\n"
        )

    monkeypatch.setattr(bis, "get_text", fake)
    out = bis.fetch(_series(dataset="WS_SPP"))
    got = {(r.country, r.year): r.value for r in out.itertuples()}
    assert got[("CHN", 2020)] == 102.0
    assert got[("JPN", 2020)] == 92.0


def test_bis_missing_country_is_a_coverage_gap_not_a_failure(monkeypatch, capsys):
    # Only CN and JP available; the other FETCH_COUNTRIES 404. fetch must still
    # return CN/JP and note the rest, not raise.
    monkeypatch.setattr(bis, "get_text", _tc_provider({"CN", "JP"}))
    out = bis.fetch(_series(borrowers="H"))
    assert set(out["country"]) == {"CHN", "JPN"}
    assert "no data for" in capsys.readouterr().err


def test_bis_all_missing_raises(monkeypatch):
    monkeypatch.setattr(bis, "get_text", _tc_provider(set()))
    with pytest.raises(RuntimeError, match="no rows"):
        bis.fetch(_series(borrowers="H"))


def test_bis_rejects_wrong_dimension_values(monkeypatch):
    def fake(url, params):
        cty = _iso2_in_url(url)
        # returns borrower P when H was asked for
        return _TC_COLS + f"Q,{cty},P,A,M,770,2020-Q1,50\n"

    monkeypatch.setattr(bis, "get_text", fake)
    with pytest.raises(RuntimeError, match="did not resolve to the intended series"):
        bis.fetch(_series(borrowers="H"))


def test_bis_rejects_csv_without_dimension_columns(monkeypatch):
    monkeypatch.setattr(
        bis, "get_text", lambda url, params: "TIME_PERIOD,OBS_VALUE\n2020-Q1,50\n"
    )
    with pytest.raises(RuntimeError, match="missing expected dimension columns"):
        bis.fetch(_series(borrowers="H"))
