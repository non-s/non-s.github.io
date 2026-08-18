"""Extended cinematic post-processing effects for the Liquid Wire engine.

Every function takes and returns a ``PIL.Image.Image`` (RGB or RGBA) of the same
size, operating on numpy arrays internally. Effects are vectorised for speed and
use ``PIL.ImageFilter.GaussianBlur`` where a smooth kernel is preferable to a
manual box blur.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PIL import Image, ImageFilter

PostProcessFn = Callable[..., Image.Image]


def _to_rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB") if img.mode != "RGB" else img


def _restore_mode(img: Image.Image, original: Image.Image) -> Image.Image:
    if original.mode == "RGBA":
        rgb = img.convert("RGB")
        alpha = original.split()[-1] if original.mode == "RGBA" else None
        if alpha is not None:
            return Image.merge("RGBA", (*rgb.split(), alpha))
    return img


def _luminance(arr: np.ndarray) -> np.ndarray:
    return 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]


def lens_flare(
    img: Image.Image,
    intensity: float = 1.0,
    position: tuple[float, float] | None = None,
    flare_type: str = "anamorphic",
) -> Image.Image:
    """Lens flare: bright halo plus horizontal anamorphic streaks or starburst."""
    base = _to_rgb(img)
    w, h = base.size
    if position is None:
        position = (w * 0.7, h * 0.3)
    px, py = float(position[0]), float(position[1])
    arr = np.asarray(base, dtype=np.float32) / 255.0

    yy, xx = np.ogrid[:h, :w]
    dist = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
    halo = np.exp(-dist / (max(w, h) * 0.12 * (0.6 + 0.4 * intensity)))
    flare = np.zeros_like(arr)
    for c in range(3):
        flare[..., c] = halo * (0.9 if c == 1 else 0.6)

    if flare_type == "anamorphic":
        streak = np.zeros((h, w), dtype=np.float32)
        half = int(w * 0.25 * intensity)
        for off in range(-half, half + 1):
            falloff = np.exp(-(off ** 2) / (2.0 * (half * 0.35 + 1.0) ** 2))
            x0 = int(np.clip(px + off, 0, w - 1))
            streak[:, x0] += falloff
        streak = np.clip(streak, 0.0, 1.0)
        for c in range(3):
            flare[..., c] += streak * (0.85 if c == 1 else 0.35) * np.exp(
                -((yy - py) ** 2) / (2.0 * (h * 0.04 + 1.0) ** 2)
            )
    else:
        for ang in np.linspace(0, np.pi, 6, endpoint=False):
            dx, dy = np.cos(ang), np.sin(ang)
            proj = (xx - px) * dx + (yy - py) * dy
            perp = np.abs((xx - px) * (-dy) + (yy - py) * dx)
            ray = np.exp(-perp / 4.0) * np.exp(-np.abs(proj) / (w * 0.4))
            for c in range(3):
                flare[..., c] += ray * (0.6 if c == 1 else 0.3)

    blended = np.clip(arr + flare * float(intensity), 0.0, 1.0)
    out = Image.fromarray((blended * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def god_rays(
    img: Image.Image,
    intensity: float = 1.0,
    source_pos: tuple[float, float] = (0.5, 0.1),
) -> Image.Image:
    """God rays: volumetric light beams diverging from a source point."""
    base = _to_rgb(img)
    w, h = base.size
    sx, sy = source_pos[0] * w, source_pos[1] * h
    arr = np.asarray(base, dtype=np.float32) / 255.0
    lum = _luminance(arr)
    bright = np.clip(lum - 0.55, 0.0, 1.0)

    yy, xx = np.ogrid[:h, :w]
    dx = xx - sx
    dy = yy - sy
    angle = np.arctan2(dy, dx)
    dist = np.sqrt(dx * dx + dy * dy) + 1.0
    rays = np.zeros_like(lum)
    n_rays = 48
    for i in range(n_rays):
        a = i * (2.0 * np.pi / n_rays) + 0.0
        align = np.cos(angle - a)
        beam = np.clip(align, 0.0, 1.0) ** 32 * np.exp(-dist / (max(w, h) * 0.9))
        rays += beam
    rays = np.clip(rays / n_rays * 4.0, 0.0, 1.0)
    ray_field = rays * (0.3 + 0.7 * bright) * float(intensity)
    blended = np.clip(arr + ray_field[..., None] * np.array([1.0, 0.95, 0.8]), 0.0, 1.0)
    out = Image.fromarray((blended * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def halation(
    img: Image.Image,
    intensity: float = 1.0,
    threshold: float = 0.7,
) -> Image.Image:
    """Film halation: red/pink halo around bright highlights (not bloom)."""
    base = _to_rgb(img)
    arr = np.asarray(base, dtype=np.float32) / 255.0
    lum = _luminance(arr)
    mask = (lum > threshold).astype(np.float32)
    halo_color = np.array([1.0, 0.4, 0.55], dtype=np.float32)
    bright = (arr * mask[..., None] * halo_color).clip(0.0, 1.0)
    if int(mask.sum()) == 0:
        return _restore_mode(base, img)
    halo_img = Image.fromarray((bright * 255.0).astype(np.uint8), "RGB").filter(
        ImageFilter.GaussianBlur(max(1.0, 12.0 * float(intensity)))
    )
    halo_arr = np.asarray(halo_img, dtype=np.float32) / 255.0
    blended = arr + halo_arr * float(intensity)
    blended = np.clip(blended, 0.0, 1.0)
    out = Image.fromarray((blended * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


_LUTS = {
    "teal_orange": np.array([0.0, 0.12, -0.12, -0.05, 0.0, 0.05, 0.10, -0.10, 0.0]),
    "bleach_bypass": np.array([-0.18, -0.18, -0.18, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "cross_process": np.array([0.10, -0.08, 0.20, -0.12, 0.05, -0.05, 0.05, 0.10, -0.18]),
    "vintage": np.array([0.15, 0.02, -0.10, -0.05, 0.05, 0.0, -0.08, -0.05, 0.05]),
}


def color_grade(
    img: Image.Image,
    intensity: float = 1.0,
    lut: str = "teal_orange",
) -> Image.Image:
    """Procedural color grading via a 3x3 channel matrix per LUT name."""
    base = _to_rgb(img)
    arr = np.asarray(base, dtype=np.float32) / 255.0
    matrix = _LUTS.get(lut, _LUTS["teal_orange"]).reshape(3, 3)
    identity = np.eye(3, dtype=np.float32)
    mix = identity + (matrix - identity) * float(intensity)
    graded = arr @ mix.T
    contrast = 1.0 + 0.10 * float(intensity)
    graded = (graded - 0.5) * contrast + 0.5
    graded = np.clip(graded, 0.0, 1.0)
    out = Image.fromarray((graded * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def anamorphic_flare(
    img: Image.Image,
    intensity: float = 1.0,
    streak_count: int = 3,
) -> Image.Image:
    """Anamorphic horizontal streak flare seeded by bright highlights."""
    base = _to_rgb(img)
    w, h = base.size
    arr = np.asarray(base, dtype=np.float32) / 255.0
    lum = _luminance(arr)
    threshold = 0.82
    mask = (lum > threshold).astype(np.float32)
    if int(mask.sum()) == 0:
        return _restore_mode(base, img)

    ys, xs = np.nonzero(mask)
    streak = np.zeros((h, w), dtype=np.float32)
    half = int(w * 0.18 * float(intensity))
    for cx, cy in zip(xs, ys, strict=True):
        for k in range(streak_count):
            offset = (k - (streak_count - 1) / 2.0) * h * 0.04
            for off in range(-half, half + 1):
                falloff = np.exp(-(off ** 2) / (2.0 * (half * 0.3 + 1.0) ** 2))
                x0 = int(np.clip(cx + off, 0, w - 1))
                y0 = int(np.clip(cy + offset, 0, h - 1))
                if 0 <= y0 < h:
                    streak[y0, x0] += falloff / (abs(k) + 1.0)
    streak = np.clip(streak, 0.0, 1.0) * float(intensity)
    tint = np.array([0.4, 0.7, 1.0], dtype=np.float32)
    blended = np.clip(arr + streak[..., None] * tint, 0.0, 1.0)
    out = Image.fromarray((blended * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def film_halation(
    img: Image.Image,
    intensity: float = 1.0,
    spread: float = 15,
) -> Image.Image:
    """Analogue film highlight diffusion in the red channel specifically."""
    base = _to_rgb(img)
    arr = np.asarray(base, dtype=np.float32) / 255.0
    lum = _luminance(arr)
    mask = (lum > 0.7).astype(np.float32)
    red_high = (arr[..., 0] * mask).clip(0.0, 1.0)
    if int(mask.sum()) == 0:
        return _restore_mode(base, img)
    red_img = Image.fromarray((red_high * 255.0).astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(max(1.0, float(spread)))
    )
    red_diff = np.asarray(red_img, dtype=np.float32) / 255.0
    boost = red_diff * float(intensity)
    out_arr = arr.copy()
    out_arr[..., 0] = np.clip(out_arr[..., 0] + boost, 0.0, 1.0)
    out_arr[..., 1] = np.clip(out_arr[..., 1] + boost * 0.25, 0.0, 1.0)
    out_arr[..., 2] = np.clip(out_arr[..., 2] + boost * 0.15, 0.0, 1.0)
    out = Image.fromarray((out_arr * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out, img)


def optical_aberration(
    img: Image.Image,
    intensity: float = 1.0,
    aberration_type: str = "spherical",
) -> Image.Image:
    """Optical aberrations: spherical, coma, or astigmatism."""
    base = _to_rgb(img)
    w, h = base.size
    arr = np.asarray(base, dtype=np.float32)
    cx, cy = w * 0.5, h * 0.5

    if aberration_type == "spherical":
        blurred = base.filter(ImageFilter.GaussianBlur(max(0.5, 4.0 * float(intensity))))
        blur_arr = np.asarray(blurred, dtype=np.float32)
        yy, xx = np.ogrid[:h, :w]
        dist = np.sqrt(((xx - cx) / (w * 0.5)) ** 2 + ((yy - cy) / (h * 0.5)) ** 2)
        feather = np.clip((dist - 0.55) / 0.45, 0.0, 1.0).astype(np.float32)
        mask = feather[..., None] * float(intensity)
        out_arr = arr * (1.0 - mask) + blur_arr * mask
        out_arr = np.clip(out_arr, 0.0, 255.0).astype(np.uint8)
        out = Image.fromarray(out_arr, "RGB")
        return _restore_mode(out, img)

    if aberration_type == "coma":
        yy, xx = np.ogrid[:h, :w]
        dx = (xx - cx) / (w * 0.5)
        dy = (yy - cy) / (h * 0.5)
        r = np.sqrt(dx * dx + dy * dy) + 1e-3
        tail_x = (dx / r) * r ** 2 * 8.0 * float(intensity)
        tail_y = (dy / r) * r ** 2 * 8.0 * float(intensity)
        ix = np.clip(np.round(xx + tail_x).astype(np.int64), 0, w - 1)
        iy = np.clip(np.round(yy + tail_y).astype(np.int64), 0, h - 1)
        out_arr = arr[iy, ix]
        out_arr = np.clip(out_arr, 0.0, 255.0).astype(np.uint8)
        out = Image.fromarray(out_arr, "RGB")
        return _restore_mode(out, img)

    yy, xx = np.ogrid[:h, :w]
    blur_y = base.filter(ImageFilter.GaussianBlur((0.5, max(0.5, 5.0 * float(intensity)))))
    blur_x = base.filter(ImageFilter.GaussianBlur((max(0.5, 5.0 * float(intensity)), 0.5)))
    arr_y = np.asarray(blur_y, dtype=np.float32)
    arr_x = np.asarray(blur_x, dtype=np.float32)
    angle = np.arctan2(yy - cy, xx - cx)
    horiz = (np.abs(np.cos(angle)) ** 2).astype(np.float32)
    vert = (np.abs(np.sin(angle)) ** 2).astype(np.float32)
    mix = float(intensity)
    out_arr = arr * (1.0 - mix) + (arr_x * horiz[..., None] + arr_y * vert[..., None]) * mix
    out_arr = np.clip(out_arr, 0.0, 255.0).astype(np.uint8)
    out = Image.fromarray(out_arr, "RGB")
    return _restore_mode(out, img)


def bokeh(
    img: Image.Image,
    intensity: float = 1.0,
    focus_point: tuple[float, float] = (0.5, 0.5),
    blur: float = 8,
    blades: int = 6,
) -> Image.Image:
    """Realistic bokeh: hexagonal-bladed defocus away from the focus point."""
    base = _to_rgb(img)
    w, h = base.size
    fx, fy = focus_point[0] * w, focus_point[1] * h
    arr = np.asarray(base, dtype=np.float32) / 255.0

    yy, xx = np.ogrid[:h, :w]
    dist = np.sqrt(((xx - fx) / (w * 0.5)) ** 2 + ((yy - fy) / (h * 0.5)) ** 2)
    blur_amount = np.clip(dist * float(blur) * float(intensity), 0.0, 24.0)
    max_blur = float(np.max(blur_amount)) if np.max(blur_amount) > 0 else 1.0
    n_levels = max(2, int(np.ceil(max_blur)) + 1)
    blurred_levels = []
    for i in range(n_levels):
        r = float(i)
        if r < 0.5:
            blurred_levels.append(arr)
            continue
        kernel = _bokeh_kernel(int(blades), int(round(r * 2 + 1)))
        conv = _convolve_separable(arr, kernel)
        blurred_levels.append(conv)

    out = np.zeros_like(arr)
    idx = np.clip(np.round(blur_amount).astype(np.int64), 0, n_levels - 1)
    for c in range(3):
        chan = np.stack([lvl[..., c] for lvl in blurred_levels], axis=-1)
        out[..., c] = np.take_along_axis(chan, idx[..., None], axis=-1)[..., 0]
    out = np.clip(out, 0.0, 1.0)
    out_img = Image.fromarray((out * 255.0).astype(np.uint8), "RGB")
    return _restore_mode(out_img, img)


def _bokeh_kernel(blades: int, size: int) -> np.ndarray:
    """Build a hexagonal (or polygonal) bokeh kernel of the given size."""
    size = max(3, size | 1)
    half = size // 2
    yy, xx = np.ogrid[:size, :size]
    dx = xx - half
    dy = yy - half
    r = np.sqrt(dx * dx + dy * dy)
    angle = np.arctan2(dy, dx)
    aperture = 2.0 * np.pi / max(3, blades)
    sector = np.abs(np.mod(angle + aperture / 2.0, aperture) - aperture / 2.0)
    radial = r * np.cos(sector)
    radius = half
    kernel = (radial <= radius).astype(np.float32)
    total = kernel.sum()
    if total > 0:
        kernel /= total
    return kernel


def _convolve_separable(arr: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Approximate 2D convolution via separable decomposition when possible."""
    size = kernel.shape[0]
    if size <= 1:
        return arr
    h, w, _ = arr.shape
    pad = size // 2
    padded = np.pad(arr, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    acc = np.zeros_like(arr)
    for i in range(size):
        for j in range(size):
            weight = float(kernel[i, j])
            if weight == 0.0:
                continue
            acc += padded[i : i + h, j : j + w] * weight
    return acc


POST_PROCESS_EXTENDED: dict[str, PostProcessFn] = {
    "lens_flare": lens_flare,
    "god_rays": god_rays,
    "halation": halation,
    "color_grade": color_grade,
    "anamorphic_flare": anamorphic_flare,
    "film_halation": film_halation,
    "optical_aberration": optical_aberration,
    "bokeh": bokeh,
}


def apply_extended(img: Image.Image, profile: dict) -> Image.Image:
    """Apply the extended post-processing stack declared under ``profile['post_extended']``."""
    post = profile.get("post_extended") if isinstance(profile, dict) else None
    if not isinstance(post, dict):
        return img
    out = img
    for name, cfg in post.items():
        if not isinstance(cfg, dict) or not cfg.get("enabled"):
            continue
        fn = POST_PROCESS_EXTENDED.get(name)
        if fn is None:
            continue
        intensity = float(cfg.get("intensity", 1.0))
        kwargs = {k: v for k, v in cfg.items() if k not in {"enabled", "intensity"}}
        try:
            out = fn(out, intensity=intensity, **kwargs)
        except TypeError:
            out = fn(out, intensity=intensity)
    return out
