#!/usr/bin/env python3
"""Convert images in assets/images/posts/ to WebP format."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

IMAGES_DIR   = Path(os.environ.get("IMAGES_DIR", "assets/images/posts"))
WEBP_QUALITY = int(os.environ.get("IMAGE_WEBP_QUALITY", "82"))
WEBP_METHOD  = int(os.environ.get("IMAGE_WEBP_METHOD", "6"))


def main() -> None:
    if not IMAGES_DIR.exists():
        log.info("No images directory found: %s", IMAGES_DIR)
        return

    from PIL import Image

    converted = skipped = failed = 0
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for img_path in sorted(IMAGES_DIR.glob(ext)):
            webp_path = img_path.with_suffix(".webp")
            if webp_path.exists():
                skipped += 1
                continue
            try:
                with Image.open(img_path) as img:
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    img.save(str(webp_path), "webp", quality=WEBP_QUALITY, method=WEBP_METHOD)

                original_size = img_path.stat().st_size
                webp_size     = webp_path.stat().st_size
                if webp_size >= original_size:
                    webp_path.unlink()
                    log.info("Skipped (WebP not smaller): %s", img_path.name)
                    skipped += 1
                else:
                    saving_pct = 100 * (1 - webp_size / original_size)
                    log.info(
                        "Converted: %s → %s (%.1f%% smaller)",
                        img_path.name, webp_path.name, saving_pct,
                    )
                    converted += 1
            except Exception as exc:
                log.warning("Failed %s: %s", img_path.name, exc)
                failed += 1

    log.info("Done — %d converted, %d skipped, %d failed", converted, skipped, failed)


if __name__ == "__main__":
    main()
