from scripts.reporting_bootstrap import bootstrap


def test_reporting_bootstrap_creates_safe_noop_dirs(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_REPORTING_ENABLED", raising=False)

    report = bootstrap(tmp_path)

    assert report["status"] == "disabled_safe_noop"
    assert (tmp_path / "_data" / "reporting_import").exists()
    assert (tmp_path / "_data" / "analytics" / "reporting_backfill").exists()
