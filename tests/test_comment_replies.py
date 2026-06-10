from utils.comment_replies import build_reply_text, classify_comment, is_replyable_comment


def test_comment_reply_blocks_spammy_urls():
    assert not is_replyable_comment("check http://spam.example")


def test_comment_reply_answers_questions():
    reply = build_reply_text("Can you do volcanoes next?", {"category": "volcanoes"})

    assert classify_comment("Can you do volcanoes next?") == "question"
    assert "question" in reply.lower() or "idea" in reply.lower() or "follow-up" in reply.lower()


def test_comment_reply_thanks_positive_comments():
    reply = build_reply_text("wow this is cool", {"category": "fungi"})

    assert classify_comment("wow this is cool") == "praise"
    assert reply


def test_comment_reply_avoids_recent_duplicate():
    first = build_reply_text("what about storms?", {"category": "weather"})
    second = build_reply_text("what about storms?", {"category": "weather", "recent_reply_texts": [first]})

    assert first != second
