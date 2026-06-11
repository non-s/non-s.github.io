from utils.feature_flags import docs_coverage, flag_names, snapshot


def test_feature_flags_have_unique_names():
    names = flag_names()

    assert len(names) == len(set(names))
    assert "STUDIO_REACH_IMPORT_ENABLED" in names
    assert "QUOTA_GUARD_ENABLED" in names


def test_feature_flag_snapshot_uses_defaults():
    snap = snapshot({})

    assert snap["ADAPTIVE_CADENCE_ENABLED"] == "1"
    assert snap["SEO_METADATA_LINT_STRICT"] == "0"


def test_feature_flags_are_documented():
    coverage = docs_coverage(__import__("pathlib").Path(__file__).resolve().parent.parent)

    assert coverage["environment_doc_missing"] == []
    assert coverage["env_example_missing"] == []
