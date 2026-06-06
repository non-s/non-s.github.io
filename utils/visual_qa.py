"""Optional Gemini thumbnail reviewer for animal-only Shorts."""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
from pathlib import Path

import requests
from PIL import Image, ImageFilter, ImageStat

log = logging.getLogger(__name__)
_TIMEOUT = 25


def evaluate_local_frame(image_path: Path) -> dict:
    """Free local image-quality check for the generated frame/thumbnail.

    It does not try to identify the animal. That remains Gemini's job
    when a key exists. This catches cheap production problems that are
    visible without any API: very dark frames, flat contrast, blur-like
    low detail, and empty/corrupt files.
    """
    try:
        with Image.open(image_path) as im:
            rgb = im.convert("RGB")
            gray = rgb.convert("L")
            stat = ImageStat.Stat(gray)
            mean = float(stat.mean[0])
            contrast = float(stat.stddev[0])
            edges = gray.resize((96, 96)).filter(ImageFilter.FIND_EDGES)
            edge_mean = float(ImageStat.Stat(edges).mean[0])
    except Exception as exc:
        return {
            "checked": False,
            "approved": True,
            "score": 5,
            "reason": f"local visual QA unavailable: {type(exc).__name__}",
        }
    score = 10
    reasons: list[str] = []
    if mean < 35:
        score -= 3
        reasons.append("too_dark")
    elif mean > 235:
        score -= 2
        reasons.append("too_bright")
    if contrast < 28:
        score -= 3
        reasons.append("low_contrast")
    if edge_mean < 3.0:
        score -= 2
        reasons.append("low_detail")
    score = max(1, min(10, score))
    return {
        "checked": True,
        "approved": score >= 5,
        "score": score,
        "brightness": round(mean, 2),
        "contrast": round(contrast, 2),
        "edge_detail": round(edge_mean, 2),
        "reason": ",".join(reasons) or "ok",
    }


def evaluate_frame(image_path: Path, expected_subject: str) -> dict:
    """Ask Gemini whether a frame visibly matches the expected animal."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return {"checked": False, "approved": True, "reason": "GEMINI_API_KEY not configured"}
    try:
        body = image_path.read_bytes()
        if not body or len(body) > 5 * 1024 * 1024:
            return {"checked": False, "approved": True, "reason": "frame unavailable or oversized"}
        model = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.0-flash-lite").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        prompt = (
            "You are a strict visual QA reviewer for an animal-only YouTube Shorts channel. "
            f"Expected visible animal subject: {expected_subject!r}. "
            "Return JSON only with approved (boolean), subject_visible (boolean), "
            "subject_match (boolean), thumbnail_quality (integer 1-10), and reason (short string). "
            "Approve only if the image visibly contains the expected animal or an unambiguous close match. "
            "Reject people, food, objects, unrelated animals, and abstract backgrounds."
        )
        payload = {"contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {
                "mime_type": mimetypes.guess_type(image_path.name)[0] or "image/jpeg",
                "data": base64.b64encode(body).decode("ascii"),
            }},
        ]}]}
        response = requests.post(url, params={"key": key}, json=payload, timeout=_TIMEOUT)
        if response.status_code != 200:
            return {"checked": False, "approved": True, "reason": f"Gemini HTTP {response.status_code}"}
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        clean = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
        verdict = json.loads(re.search(r"\{.*\}", clean, re.DOTALL).group(0))
        return {
            "checked": True,
            "approved": bool(verdict.get("approved")),
            "subject_visible": bool(verdict.get("subject_visible")),
            "subject_match": bool(verdict.get("subject_match")),
            "thumbnail_quality": max(1, min(10, int(verdict.get("thumbnail_quality") or 1))),
            "reason": str(verdict.get("reason") or "")[:240],
        }
    except Exception as exc:
        log.debug("Gemini visual QA skipped: %s", exc)
        return {"checked": False, "approved": True, "reason": f"Gemini QA unavailable: {type(exc).__name__}"}
