from utils.comment_replies import build_reply_text, is_replyable_comment


def test_comment_reply_blocks_spammy_urls():
    assert not is_replyable_comment("check http://spam.example")


def test_comment_reply_answers_questions():
    reply = build_reply_text("Can you do volcanoes next?", {"category": "volcanoes"})

    assert "Great question" in reply
    assert "Volcanoes" in reply


def test_comment_reply_thanks_positive_comments():
    reply = build_reply_text("wow this is cool", {"category": "fungi"})

    assert "More wild nature clues" in reply
