import json

from utils.music_bed import rank_manifest_tracks


def test_rank_manifest_tracks_scores_safe_local_manifest(tmp_path):
    asset = tmp_path / "bed.mp3"
    asset.write_bytes(b"x" * 100_000)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "tracks": [
                    {
                        "name": "Bed",
                        "asset_path": "bed.mp3",
                        "mood": "wonder",
                        "bpm_bucket": "medium",
                        "safe_for_short": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    ranked = rank_manifest_tracks({"category": "cats"}, manifest)

    assert ranked[0]["name"] == "Bed"
    assert ranked[0]["content_id_safe_music"] is True
