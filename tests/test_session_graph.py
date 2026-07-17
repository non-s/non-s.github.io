from utils.session_graph import pinned_comment_payload


def test_pinned_comment_payload_uses_handoff():
    text = pinned_comment_payload({}, {"title": "Next Short", "url": "https://youtu.be/x"})

    assert "Next Short" in text
    assert "https://youtu.be/x" in text


def test_pinned_comment_payload_falls_back_without_handoff():
    text = pinned_comment_payload({"series": "Lofi Nights"})

    assert "Lofi Nights" in text
