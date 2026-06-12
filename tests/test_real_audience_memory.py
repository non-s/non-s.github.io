from utils.audience_memory import build_audience_memory
from utils.real_metrics import enrich_markers_with_latest


def test_enrich_markers_with_latest_adds_real_analytics():
    markers = [{"video_id": "abc", "title": "Old", "category": "fungi"}]
    latest = {
        "top_performers": [
            {
                "video_id": "abc",
                "views": 1200,
                "average_view_percentage": 81.5,
                "average_view_duration": 18.0,
                "subscribers_gained": 4,
                "story_format": "hidden_network",
            }
        ]
    }

    youtube = {"video_audit": {"top_public_videos": [{"video_id": "abc", "likes": 20, "comments": 3}]}}

    out = enrich_markers_with_latest(markers, latest, youtube)[0]

    assert out["analytics"]["views"] == 1200
    assert out["analytics"]["comments"] == 3
    assert out["analytics"]["averageViewPercentage"] == 81.5
    assert out["story_format"] == "hidden_network"


def test_audience_memory_weights_real_subscriber_conversion():
    markers = []
    for idx in range(5):
        markers.append(
            {
                "video_id": f"f{idx}",
                "title": "Fungi",
                "category": "fungi",
                "story_format": "hidden_network",
                "series": "Hidden Network",
                "analytics": {
                    "views": 1000,
                    "comments": 12,
                    "averageViewPercentage": 82,
                    "averageViewDuration": 18,
                    "subscribersGained": 5,
                },
            }
        )
    for idx in range(5):
        markers.append(
            {
                "video_id": f"d{idx}",
                "title": "Dogs",
                "category": "dogs",
                "story_format": "single_fact",
                "series": "Pet Signals",
                "analytics": {
                    "views": 1000,
                    "comments": 0,
                    "averageViewPercentage": 38,
                    "averageViewDuration": 8,
                    "subscribersGained": 0,
                },
            }
        )

    memory = build_audience_memory(markers)

    assert memory["coverage"]["with_retention"] == 10
    assert memory["weights"]["category_subscribers"]["fungi"] > 1
    assert memory["weights"]["category_retention"]["dogs"] < 1
    assert memory["winners"]["series"][0]["value"] == "Hidden Network"


def test_audience_memory_does_not_weight_small_samples():
    markers = [
        {
            "video_id": f"f{idx}",
            "title": "Fungi",
            "category": "fungi",
            "story_format": "hidden_network",
            "series": "Hidden Network",
            "analytics": {
                "views": 1000,
                "comments": 12,
                "averageViewPercentage": 82,
                "averageViewDuration": 18,
                "subscribersGained": 5,
            },
        }
        for idx in range(3)
    ]

    memory = build_audience_memory(markers)

    assert memory["category"]["fungi"]["confidence"]["recommendation_strength"] == "observe"
    assert "fungi" not in memory["weights"]["category_subscribers"]
