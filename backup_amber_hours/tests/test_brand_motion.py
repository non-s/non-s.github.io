"""Tests for utils/brand_motion.py."""

from __future__ import annotations

import pytest
from PIL import Image

from utils.brand_motion import (
    animated_rain,
    animated_stars,
    lightning_flash,
    pulsing_glow,
    rising_steam,
    turntable_spin_offset,
)


def test_animated_rain_phase_0_equals_phase_1():
    a = animated_rain(200, 300, 50, seed=1, phase=0.0, cycles=2)
    b = animated_rain(200, 300, 50, seed=1, phase=1.0, cycles=2)
    assert list(a.getdata()) == list(b.getdata())


def test_animated_stars_phase_0_equals_phase_1():
    a = animated_stars(200, 300, 40, seed=2, phase=0.0, cycles=3)
    b = animated_stars(200, 300, 40, seed=2, phase=1.0, cycles=3)
    assert list(a.getdata()) == list(b.getdata())


def test_pulsing_glow_phase_0_equals_phase_1():
    a = pulsing_glow(200, 300, 100, 150, 80, 0.0, (241, 157, 85), cycles=1)
    b = pulsing_glow(200, 300, 100, 150, 80, 1.0, (241, 157, 85), cycles=1)
    assert list(a.getdata()) == list(b.getdata())


def test_rising_steam_phase_0_equals_phase_1():
    a = rising_steam(200, 300, 100, 200, 0.0, cycles=1, rise_height=60)
    b = rising_steam(200, 300, 100, 200, 1.0, cycles=1, rise_height=60)
    assert list(a.getdata()) == list(b.getdata())


def test_turntable_spin_offset_phase_0_equals_phase_1():
    a = turntable_spin_offset(20, 0.0, cycles=1)
    b = turntable_spin_offset(20, 1.0, cycles=1)
    assert a[0] == pytest.approx(b[0], abs=1e-9)
    assert a[1] == pytest.approx(b[1], abs=1e-9)


def test_lightning_flash_peaks_at_the_flash_phase():
    layer = lightning_flash(100, 100, 0.5, (0.5,))
    assert layer.getpixel((0, 0))[3] == 200


def test_lightning_flash_is_transparent_far_from_any_flash():
    layer = lightning_flash(100, 100, 0.2, (0.7,))
    assert layer.getpixel((0, 0))[3] == 0


def test_lightning_flash_is_loop_safe_across_the_seam():
    """A flash placed right at phase 0.0 must look the same approaching
    from phase 1.0 as it does at phase 0.0 -- the wrap-aware distance
    calculation is what makes this safe regardless of placement."""
    near_start = lightning_flash(50, 50, 0.001, (0.0,))
    near_end = lightning_flash(50, 50, 0.999, (0.0,))
    assert near_start.getpixel((0, 0)) == near_end.getpixel((0, 0))


def test_lightning_flash_returns_expected_size_and_mode():
    layer = lightning_flash(64, 32, 0.5, (0.5,))
    assert layer.size == (64, 32)
    assert layer.mode == "RGBA"
    assert isinstance(layer, Image.Image)
