"""Per-frame post-processing effects for the Liquid Wire engine.

Every function takes and returns a ``PIL.Image.Image`` (RGB or RGBA) of the same
size, using only numpy/PIL/stdlib so no new dependencies are introduced.
``apply_all`` dispatches based on a ``post`` profile dict where each effect has
a boolean ``enabled`` flag and a float ``intensity`` in [0, 1].
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter


def _to_rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB") if img.mode != "RGB" else img


def _restore_mode(img: Image.Image, original: Image.Image) -> Image.Image:
    if original.mode == "RGBA":
        rgb = img.convert("RGB")
        alpha = original.split()[-1] if original.mode == "RGBA" else None
        if alpha is not None:
            return Image.merge("RGBA", (*rgb.split(), alpha))
    return img


def bloom(img: Image.Image, threshold: float = 0.7, blur_radius: float = 15, intensity: float = 0.6) -> Image.Image:
    """Extract bright pixels, blur them, and screen-blend back onto the image."""
    base = _to_rgb(img)
    arr = np.asarray(base, dtype=np.float32) / 255.0
    luminance = arr.mean(axis=2)
    mask = (luminance > threshold).astype(np.float32)[..., None]
    bright = (arr * mask * 255.0).clip(0, 255).astype(np.uint8)
    if int(mask.sum()) == 0:
        # Nothing bright enough: early-out to avoid wasted work.
        return _restore_mode(base, img)
    bright_img = Image.fromarray(bright, "RGB").filter(ImageFilter.GaussianBlur(max(0.1, float(blur_radius))))
    bright_arr = np.asarray(bright_img, dtype=np.float32) / 255.0
    blended = arr + bright_arr * float(intensity)
    blended = np.clip(blended, 0.0, 1.0)
    out = Image.fromarray((blended * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def depth_of_field(img: Image.Image, focus_radius: float = 0.3, blur_strength: float = 8) -> Image.Image:
    """Radial blur away from the centre; the inner ``focus_radius`` stays sharp."""
    base = _to_rgb(img)
    w, h = base.size
    blurred = base.filter(ImageFilter.GaussianBlur(float(blur_strength)))
    yy, xx = np.ogrid[:h, :w]
    cx, cy = w * 0.5, h * 0.5
    dist = np.sqrt(((xx - cx) / (w * 0.5)) ** 2 + ((yy - cy) / (h * 0.5)) ** 2)
    feather = np.clip((dist - focus_radius) / max(1e-3, 1.0 - focus_radius), 0.0, 1.0).astype(np.float32)
    sharp_arr = np.asarray(base, dtype=np.float32)
    blur_arr = np.asarray(blurred, dtype=np.float32)
    mask = feather[..., None]
    blended = sharp_arr * (1.0 - mask) + blur_arr * mask
    out = Image.fromarray(blended.astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def film_grain(img: Image.Image, intensity: float = 0.04) -> Image.Image:
    """Add subtle Poisson-like noise across the frame."""
    base = _to_rgb(img)
    arr = np.asarray(base, dtype=np.float32)
    rng = np.random.default_rng(0)  # static seed keeps grain stable per frame
    # Poisson-shaped noise via normal approximation of Poisson(lambda) centering.
    noise: np.ndarray = np.asarray(rng.normal(0.0, 1.0, arr.shape), dtype=np.float32)
    grain = (np.sqrt(np.maximum(arr, 0.0)) * noise) * float(intensity) * 255.0
    out_arr = np.clip(arr + grain, 0.0, 255.0).astype(np.uint8)
    out = Image.fromarray(out_arr, "RGB")
    return _restore_mode(out, img)


def chromatic_aberration(img: Image.Image, strength: float = 2.0) -> Image.Image:
    """Offset RGB channels radially from the centre so edges split colour."""
    base = _to_rgb(img)
    w, h = base.size
    arr = np.asarray(base, dtype=np.float32)
    # Build a per-pixel coordinate grid (h, w).
    xs = np.arange(w, dtype=np.float32)[None, :] * np.ones((h, 1), dtype=np.float32)
    ys = np.arange(h, dtype=np.float32)[:, None] * np.ones((1, w), dtype=np.float32)
    cx, cy = w * 0.5, h * 0.5
    dx = (xs - cx) / (w * 0.5)
    dy = (ys - cy) / (h * 0.5)
    shift_x = (dx * float(strength)).astype(np.float32)
    shift_y = (dy * float(strength)).astype(np.float32)
    # Red channel pulled outward, blue channel pushed inward (or vice versa).
    ix_r = np.clip(np.round(xs + shift_x).astype(np.int64), 0, w - 1)
    iy_r = np.clip(np.round(ys + shift_y).astype(np.int64), 0, h - 1)
    ix_b = np.clip(np.round(xs - shift_x).astype(np.int64), 0, w - 1)
    iy_b = np.clip(np.round(ys - shift_y).astype(np.int64), 0, h - 1)
    r = arr[..., 0][iy_r, ix_r]
    b = arr[..., 2][iy_b, ix_b]
    out_arr = np.stack([r, arr[..., 1], b], axis=-1)
    out_arr = np.clip(out_arr, 0.0, 255.0).astype(np.uint8)
    out = Image.fromarray(out_arr, "RGB")
    return _restore_mode(out, img)


def vignette(img: Image.Image, strength: float = 0.3) -> Image.Image:
    """Radial darkening toward the corners."""
    base = _to_rgb(img)
    w, h = base.size
    arr = np.asarray(base, dtype=np.float32)
    yy, xx = np.ogrid[:h, :w]
    cx, cy = w * 0.5, h * 0.5
    dist = np.sqrt(((xx - cx) / (w * 0.5)) ** 2 + ((yy - cy) / (h * 0.5)) ** 2)
    falloff = np.clip(dist, 0.0, 1.4) ** 2
    factor = (1.0 - float(strength) * falloff)[..., None].astype(np.float32)
    out_arr = np.clip(arr * factor, 0.0, 255.0).astype(np.uint8)
    out = Image.fromarray(out_arr, "RGB")
    return _restore_mode(out, img)


def hdr_tone_map(img: Image.Image, exposure: float = 1.2, shoulder: float = 0.9) -> Image.Image:
    """HDR-style tone mapping (filmic ACES-like) for richer highlights.

    Applies exposure gain then a filmic shoulder curve that smoothly
    compresses highlights above 1.0, giving a cinematic look without
    harsh clipping.
    """
    base = _to_rgb(img)
    arr = np.asarray(base, dtype=np.float32) / 255.0
    exposed = arr * float(exposure)
    # ACES filmic approximation (Narkowicz 2015, simplified).
    a = 2.51
    b = 0.03
    c = 2.43
    d = 0.59
    e = 0.14 * float(shoulder)
    mapped = (exposed * (a * exposed + b)) / (exposed * (c * exposed + d) + e)
    mapped = np.clip(mapped, 0.0, 1.0)
    out = Image.fromarray((mapped * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def depth_fog(img: Image.Image, fog_color: tuple = (0, 0, 0), density: float = 0.15) -> Image.Image:
    """Atmospheric depth fog that darkens and tints the frame edges.

    Simulates a volumetric fog that thickens toward the borders, adding
    depth and atmosphere to the void around the wireframe object.
    """
    base = _to_rgb(img)
    w, h = base.size
    arr = np.asarray(base, dtype=np.float32)
    yy, xx = np.ogrid[:h, :w]
    cx, cy = w * 0.5, h * 0.5
    dist = np.sqrt(((xx - cx) / (w * 0.5)) ** 2 + ((yy - cy) / (h * 0.5)) ** 2)
    fog_factor = np.clip(dist * float(density), 0.0, 1.0).astype(np.float32)
    fog_arr = np.array(fog_color, dtype=np.float32)
    blended = arr * (1.0 - fog_factor[..., None]) + fog_arr * fog_factor[..., None]
    out_arr = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    out = Image.fromarray(out_arr, "RGB")
    return _restore_mode(out, img)


def motion_blur(img: Image.Image, angle: float = 0.0, strength: float = 5.0) -> Image.Image:
    """Directional motion blur via a weighted kernel approximation.

    Simulates camera/object motion by smearing pixels along a direction.
    Uses a multi-tap averaged shift for an efficient approximation of a
    linear motion blur kernel.
    """
    base = _to_rgb(img)
    if strength <= 0.5:
        return _restore_mode(base, img)
    w, h = base.size
    arr = np.asarray(base, dtype=np.float32)
    n_taps = max(3, int(strength))
    angle_rad = float(angle) * np.pi / 180.0
    dx = np.cos(angle_rad)
    dy = np.sin(angle_rad)
    accum = arr.copy()
    for i in range(1, n_taps + 1):
        offset = float(i) * float(strength) / float(n_taps)
        sx = int(round(dx * offset))
        sy = int(round(dy * offset))
        shifted = np.zeros_like(arr)
        x0 = max(0, sx)
        x1 = min(w, w + sx)
        y0 = max(0, sy)
        y1 = min(h, h + sy)
        sx_src = max(0, -sx)
        sy_src = max(0, -sy)
        shifted[y0:y1, x0:x1] = arr[sy_src : sy_src + (y1 - y0), sx_src : sx_src + (x1 - x0)]
        accum += shifted
    accum /= float(n_taps + 1)
    out_arr = np.clip(accum, 0.0, 255.0).astype(np.uint8)
    out = Image.fromarray(out_arr, "RGB")
    return _restore_mode(out, img)


def filmic_grain(img: Image.Image, intensity: float = 0.04) -> Image.Image:
    """Alias for film_grain (kept for naming consistency)."""
    return film_grain(img, intensity=intensity)


def apply_all(img: Image.Image, profile: dict) -> Image.Image:
    """Apply the post-processing stack defined by ``profile['post']``.

    Each effect entry is ``{"enabled": bool, "intensity": float}`` where
    ``intensity`` in [0, 1] scales the effect's strength. Effects are applied in
    a fixed order chosen for visual stability: chromatic aberration, bloom,
    depth of field, HDR tone mapping, depth fog, motion blur, film grain,
    vignette.
    """
    post = profile.get("post") if isinstance(profile, dict) else None
    if not isinstance(post, dict):
        return img
    out = img

    ca = post.get("chromatic_aberration")
    if isinstance(ca, dict) and ca.get("enabled") and ca.get("intensity", 0.0) > 0.0:
        out = chromatic_aberration(out, strength=2.0 * float(ca.get("intensity", 1.0)))

    bl = post.get("bloom")
    if isinstance(bl, dict) and bl.get("enabled") and bl.get("intensity", 0.0) > 0.0:
        out = bloom(out, intensity=0.6 * float(bl.get("intensity", 1.0)))

    dof = post.get("depth_of_field")
    if isinstance(dof, dict) and dof.get("enabled") and dof.get("intensity", 0.0) > 0.0:
        out = depth_of_field(out, blur_strength=8.0 * float(dof.get("intensity", 1.0)))

    hdr = post.get("hdr_tone_map")
    if isinstance(hdr, dict) and hdr.get("enabled") and hdr.get("intensity", 0.0) > 0.0:
        out = hdr_tone_map(out, exposure=1.0 + 0.4 * float(hdr.get("intensity", 1.0)))

    fog = post.get("depth_fog")
    if isinstance(fog, dict) and fog.get("enabled") and fog.get("intensity", 0.0) > 0.0:
        out = depth_fog(out, density=0.15 * float(fog.get("intensity", 1.0)))

    mb = post.get("motion_blur")
    if isinstance(mb, dict) and mb.get("enabled") and mb.get("intensity", 0.0) > 0.0:
        angle = float(mb.get("angle", 0.0))
        out = motion_blur(out, angle=angle, strength=4.0 * float(mb.get("intensity", 1.0)))

    fg = post.get("film_grain")
    if isinstance(fg, dict) and fg.get("enabled") and fg.get("intensity", 0.0) > 0.0:
        out = film_grain(out, intensity=0.04 * float(fg.get("intensity", 1.0)))

    vg = post.get("vignette")
    if isinstance(vg, dict) and vg.get("enabled") and vg.get("intensity", 0.0) > 0.0:
        out = vignette(out, strength=0.3 * float(vg.get("intensity", 1.0)))
    return out
