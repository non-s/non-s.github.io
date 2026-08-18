from __future__ import annotations

import numpy as np
from PIL import Image

from utils.post_process import (
    apply_all,
    bloom,
    chromatic_aberration,
    depth_fog,
    depth_of_field,
    film_grain,
    hdr_tone_map,
    motion_blur,
    vignette,
)


def _solid(size: tuple[int, int] = (128, 96), color=(120, 130, 140)) -> Image.Image:
    return Image.new("RGB", size, color)


def _bright_center() -> Image.Image:
    img = Image.new("RGB", (128, 96), (0, 0, 0))
    arr = np.asarray(img, dtype=np.uint8).copy()
    arr[40:56, 56:72] = (255, 255, 255)
    return Image.fromarray(arr, "RGB")


def test_each_effect_preserves_size_and_mode() -> None:
    img = _solid()
    for out in (
        bloom(img),
        depth_of_field(img),
        film_grain(img),
        chromatic_aberration(img),
        vignette(img),
    ):
        assert out.size == img.size
        assert out.mode == "RGB"


def test_bloom_adds_brightness() -> None:
    img = _bright_center()
    out = bloom(img, threshold=0.5, blur_radius=6, intensity=0.8)
    base = np.asarray(img, dtype=np.float32).mean()
    result = np.asarray(out, dtype=np.float32).mean()
    assert result > base


def test_vignette_darkens_edges() -> None:
    img = _solid(color=(200, 200, 200))
    out = vignette(img, strength=0.9)
    arr = np.asarray(out, dtype=np.float32)
    h, w = arr.shape[:2]
    center_brightness = arr[h // 2, w // 2].mean()
    corner_brightness = arr[0, 0].mean()
    assert corner_brightness < center_brightness


def test_film_grain_adds_noise() -> None:
    img = _solid(color=(100, 100, 100))
    out = film_grain(img, intensity=0.5)
    base = np.asarray(img, dtype=np.float32)
    result = np.asarray(out, dtype=np.float32)
    diff = np.abs(result - base)
    # The flat region should acquire non-zero variation.
    assert diff.std() > 0.0


def test_chromatic_aberration_shifts_channels() -> None:
    # A horizontal red stripe near the top exercises the y-component of the
    # radial shift, which is what chromatic aberration actually redistributes.
    img = Image.new("RGB", (128, 96), (0, 0, 0))
    arr = np.asarray(img, dtype=np.uint8).copy()
    arr[10:20, :] = (255, 0, 0)
    img = Image.fromarray(arr, "RGB")
    out = chromatic_aberration(img, strength=6.0)
    base_r = np.asarray(img, dtype=np.float32)[..., 0]
    out_r = np.asarray(out, dtype=np.float32)[..., 0]
    # The red channel should spread compared to the original hard edges.
    assert not np.allclose(base_r, out_r)


def test_depth_of_field_blurs() -> None:
    arr = np.zeros((96, 128, 3), dtype=np.uint8)
    arr[::8, :] = (255, 255, 255)
    img = Image.fromarray(arr, "RGB")
    out = depth_of_field(img, focus_radius=0.1, blur_strength=5)
    base_edges = np.abs(np.diff(np.asarray(img, dtype=np.float32).mean(axis=2), axis=0)).mean()
    out_edges = np.abs(np.diff(np.asarray(out, dtype=np.float32).mean(axis=2), axis=0)).mean()
    assert out_edges < base_edges


def test_apply_all_no_post_returns_input() -> None:
    img = _solid()
    out = apply_all(img, {})
    assert out.size == img.size


def test_apply_all_runs_enabled_effects() -> None:
    img = _bright_center()
    profile = {
        "post": {
            "bloom": {"enabled": True, "intensity": 1.0},
            "vignette": {"enabled": True, "intensity": 1.0},
            "film_grain": {"enabled": False, "intensity": 1.0},
        }
    }
    out = apply_all(img, profile)
    assert out.size == img.size
    base = np.asarray(img, dtype=np.float32).mean()
    result = np.asarray(out, dtype=np.float32).mean()
    # Bloom brightens the centre, vignette darkens edges; net mean differs.
    assert abs(result - base) > 0.1 or not np.allclose(np.asarray(img), np.asarray(out))


def test_hdr_tone_map_preserves_size() -> None:
    img = _solid()
    out = hdr_tone_map(img, exposure=1.3)
    assert out.size == img.size
    assert out.mode == "RGB"


def test_hdr_tone_map_changes_brightness() -> None:
    img = _solid(color=(180, 180, 180))
    out = hdr_tone_map(img, exposure=1.5)
    assert not np.allclose(np.asarray(img), np.asarray(out))


def test_depth_fog_preserves_size() -> None:
    img = _solid()
    out = depth_fog(img, density=0.3)
    assert out.size == img.size


def test_depth_fog_darkens_edges() -> None:
    img = _solid(color=(200, 200, 200))
    out = depth_fog(img, density=0.5)
    arr = np.asarray(out, dtype=np.float32)
    center = arr[arr.shape[0] // 2, arr.shape[1] // 2].mean()
    corner = arr[0, 0].mean()
    assert corner < center


def test_motion_blur_preserves_size() -> None:
    img = _solid()
    out = motion_blur(img, angle=45.0, strength=3.0)
    assert out.size == img.size


def test_motion_blur_smears_edges() -> None:
    arr = np.zeros((96, 128, 3), dtype=np.uint8)
    arr[:, 64:] = (255, 255, 255)
    img = Image.fromarray(arr, "RGB")
    out = motion_blur(img, angle=0.0, strength=5.0)
    out_arr = np.asarray(out, dtype=np.float32)
    # The sharp vertical edge at x=64 should be smeared.
    base_edge = np.abs(np.diff(np.asarray(img, dtype=np.float32).mean(axis=2), axis=1)).max()
    out_edge = np.abs(np.diff(out_arr.mean(axis=2), axis=1)).max()
    assert out_edge < base_edge


def test_apply_all_with_new_effects() -> None:
    img = _bright_center()
    profile = {
        "post": {
            "bloom": {"enabled": True, "intensity": 0.8},
            "hdr_tone_map": {"enabled": True, "intensity": 0.5},
            "depth_fog": {"enabled": True, "intensity": 0.4},
            "motion_blur": {"enabled": True, "intensity": 0.3, "angle": 90.0},
        }
    }
    out = apply_all(img, profile)
    assert out.size == img.size
    assert np.all(np.isfinite(np.asarray(out)))
