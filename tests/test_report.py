from toy_money import datastore
from toy_money.align import resolve_alignment
from toy_money.config import MAX_YEAR
from toy_money.report import build_report


def test_build_report_uses_bundled_fallback_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(datastore, "DATA_DIR", tmp_path / "empty")
    out = tmp_path / "report.html"

    path = build_report(resolve_alignment("bubble_peak"), out)

    text = path.read_text(encoding="utf-8")
    assert "Conclusion" in text
    assert "bundled fallback snapshot" in text
    assert "crossing on 2" in text
    assert f"observations after {MAX_YEAR}" in text

