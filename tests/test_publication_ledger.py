import json

from utils.atomic_state import load_versioned
from utils.publication_ledger import publication_receipt, rebuild_publication_state


def _metadata(content_id: str, title: str) -> dict:
    return {
        "content_id": content_id,
        "title": title,
        "scene": "living wire",
        "kind": "short",
        "generated_at": "2026-08-20T10:00:00Z",
        "genome": {"family": "orb", "puzzle": {}},
        "quality_report": {"passed": True},
    }


def test_receipt_is_self_contained() -> None:
    receipt = publication_receipt("video-1", _metadata("lw-1", "Unique Bloom"), uploaded_at="2026-08-20T11:00:00Z")
    assert receipt["video_tag"]["content_id"] == "lw-1"
    assert receipt["catalog_record"]["content_id"] == "lw-1"


def test_rebuild_merges_out_of_order_receipts_idempotently(tmp_path) -> None:
    evidence, data = tmp_path / "evidence", tmp_path / "data"
    for folder, video_id, content_id, title, uploaded in (
        ("new", "v2", "lw-2", "Second Tide", "2026-08-20T12:00:00Z"),
        ("old", "v1", "lw-1", "First Bloom", "2026-08-20T11:00:00Z"),
    ):
        target = evidence / folder
        target.mkdir(parents=True)
        payload = publication_receipt(video_id, _metadata(content_id, title), uploaded_at=uploaded)
        (target / f"publication_receipt_{video_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    first = rebuild_publication_state(evidence, data)
    second = rebuild_publication_state(evidence, data)

    assert first == second == {"receipts": 2, "catalog_records": 2, "video_tags": 2}
    catalog = load_versioned(data / "catalog_memory.json", 1, {}, [])
    assert {row["content_id"] for row in catalog} == {"lw-1", "lw-2"}
    assert set(json.loads((data / "video_tags.json").read_text())) == {"v1", "v2"}
    assert json.loads((data / "used_titles.json").read_text()) == ["Second Tide", "First Bloom"]
