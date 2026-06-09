from PIL import Image, ImageDraw

from utils.visual_ctr import score_ctr_frame


def test_score_ctr_frame_prefers_detailed_center_subject(tmp_path):
    strong = tmp_path / "strong.jpg"
    img = Image.new("RGB", (360, 640), (92, 120, 95))
    draw = ImageDraw.Draw(img)
    for i in range(40):
        x = 120 + (i % 8) * 16
        y = 170 + (i // 8) * 42
        draw.rectangle((x, y, x + 34, y + 28), fill=(210, 220, 190))
        draw.line((x, y, x + 34, y + 28), fill=(20, 35, 20), width=2)
    img.save(strong)

    weak = tmp_path / "weak.jpg"
    Image.new("RGB", (360, 640), (20, 20, 20)).save(weak)

    strong_score = score_ctr_frame(strong)
    weak_score = score_ctr_frame(weak)

    assert strong_score["checked"]
    assert strong_score["score"] > weak_score["score"]
    assert strong_score["approved"]


def test_score_ctr_frame_reports_dark_flat_preview(tmp_path):
    frame = tmp_path / "flat.jpg"
    Image.new("RGB", (360, 640), (4, 4, 4)).save(frame)

    result = score_ctr_frame(frame)

    assert result["checked"]
    assert not result["approved"]
    assert "poor_brightness_for_feed" in result["reason"]
