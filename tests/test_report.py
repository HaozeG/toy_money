import json

from toy_money import datastore
from toy_money.align import resolve_alignment
from toy_money.config import MAX_YEAR
from toy_money.report import build_report


def test_build_report_uses_bundled_fallback_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(datastore, "DATA_DIR", tmp_path / "empty")
    out = tmp_path / "report.html"

    path = build_report(
        resolve_alignment("bubble_peak"), out, findings_label="bubble_peak"
    )

    text = path.read_text(encoding="utf-8")
    assert "Conclusion" in text
    assert "bundled fallback snapshot" in text
    assert f"data through {MAX_YEAR}" in text
    # headline names the scope, no direction tally
    assert "indicators" in text
    assert "above Japan on" not in text

    findings = json.loads((tmp_path / "findings.bubble_peak.json").read_text())
    assert findings["method"] == "precedent"
    assert findings["alignment"]["anchors"] == {"JPN": 1991, "CHN": 2021}
    assert findings["findings"]
    manifest = json.loads((tmp_path / "cache_manifest.json").read_text())
    assert set(manifest["series"]) >= {"gdp_growth", "gov_debt_gdp"}

