from toy_money import cli, datastore


def test_cli_seed_fetch_and_build(tmp_path, monkeypatch):
    monkeypatch.setattr(datastore, "DATA_DIR", tmp_path / "data")

    assert cli.main(["fetch", "--source", "seed", "--force"]) == 0
    assert datastore.has("gdp_growth")
    assert datastore.provenance("gdp_growth") == "seed"

    out = tmp_path / "report.html"
    assert cli.main(["build", "--out", str(out)]) == 0
    assert out.exists()
