"""Soft-body interaction fields for multi-organism wireframe scenes."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def jelly_deform(
    sx: np.ndarray,
    sy: np.ndarray,
    center: tuple[float, float],
    t: float,
    phase: float,
    softness: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply volume-preserving wobble and shear to a projected wire surface."""
    cx, cy = center
    x, y = sx - cx, sy - cy
    scale = max(80.0, float(np.sqrt(np.mean(x*x + y*y))))
    wave_x = np.sin(y / scale * 3.2 + t * 1.17 + phase)
    wave_y = np.cos(x / scale * 2.7 - t * .91 + phase * .7)
    breathe = 1.0 + .045 * softness * math.sin(t * .73 + phase)
    shear = .035 * softness * math.sin(t * .49 + phase * 1.3)
    return cx + breathe*x + shear*y + 9*softness*wave_x, cy + y/breathe + shear*x + 9*softness*wave_y


def interaction_deform(
    sx: np.ndarray,
    sy: np.ndarray,
    target: tuple[float, float],
    kind: str,
    strength: float,
    t: float,
    phase: float,
    radius: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Pull the facing skin into a viscous neck while retaining wire topology."""
    tx, ty = target
    dx, dy = tx - sx, ty - sy
    distance2 = dx*dx + dy*dy
    influence = np.exp(-distance2 / max(1.0, 2*radius*radius))
    pulse = .65 + .35 * math.sin(t * .62 + phase)
    coefficients = {
        "fusion": .36, "attraction": .22, "braid": .16, "resonance": .10,
        "orbit": .07, "mirror": .08, "emergence": .18,
    }
    pull = coefficients.get(kind, .12) * float(np.clip(strength, 0, 1)) * pulse * influence
    if kind == "braid":
        length = np.sqrt(distance2) + 1e-6
        sideways = np.sin(length / max(20.0, radius) * 8 - t*1.4 + phase) * influence * strength * 18
        sx = sx + pull*dx - sideways*dy/length
        sy = sy + pull*dy + sideways*dx/length
    elif kind == "resonance":
        ripple = np.sin(np.sqrt(distance2)/max(15.0, radius)*10 - t*2 + phase) * influence * strength * 12
        length = np.sqrt(distance2) + 1e-6
        sx, sy = sx + pull*dx - ripple*dx/length, sy + pull*dy - ripple*dy/length
    else:
        sx, sy = sx + pull*dx, sy + pull*dy
    return sx, sy


def bridge_strands(
    source: tuple[float, float],
    target: tuple[float, float],
    relation: dict[str, Any],
    t: float,
    strands: int = 7,
) -> list[list[tuple[float, float]]]:
    """Generate viscous curved filaments that make fusion visibly continuous."""
    sx, sy = source
    tx, ty = target
    dx, dy = tx-sx, ty-sy
    length = max(1.0, math.hypot(dx, dy))
    nx, ny = -dy/length, dx/length
    strength = float(relation.get("strength", .5))
    phase = float(relation.get("phase", 0))
    result = []
    for strand in range(strands):
        offset = (strand-(strands-1)/2) * (2.2 + 3.0*strength)
        points = []
        for step in range(25):
            u = step/24
            envelope = math.sin(math.pi*u)
            viscous = math.sin(u*math.pi*2 + t*.8 + phase + strand*.55)
            bend = offset*(1-envelope*.45) + envelope*viscous*(10+18*strength)
            points.append((sx+dx*u+nx*bend, sy+dy*u+ny*bend))
        result.append(points)
    return result
