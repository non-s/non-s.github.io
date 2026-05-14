#!/usr/bin/env python3
"""Convert images in assets/images/posts/ to WebP format"""
import logging
from pathlib import Path
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main():
    posts_dir = Path("assets/images/posts")
    if not posts_dir.exists():
        logging.info("No images directory found")
        return

    converted = 0
    for ext in ["*.jpg", "*.jpeg", "*.png"]:
        for img_path in posts_dir.glob(ext):
            webp_path = img_path.with_suffix(".webp")
            if webp_path.exists():
                continue
            try:
                with Image.open(img_path) as img:
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    img.save(webp_path, "webp", quality=82, method=6)
                    logging.info(f"Converted: {img_path.name} -> {webp_path.name}")
                    converted += 1
            except Exception as e:
                logging.warning(f"Failed {img_path.name}: {e}")

    logging.info(f"Done: {converted} image(s) converted")


if __name__ == "__main__":
    main()
