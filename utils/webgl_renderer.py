"""WebGL headless renderer via Playwright/Chromium.

Renders 3D scenes using WebGL ray-marching shaders in a headless Chromium
browser, capturing each frame as a PNG. This replaces the CPU numpy/PIL
wireframe path with GPU-accelerated PBR rendering: filled surfaces,
soft shadows, ambient occlusion, Fresnel rim light and ACES tone mapping.

Public API:
- ``WebGLRenderer`` — manages the Chromium browser and canvas.
- ``render_frame(params) -> bytes`` — render one frame, returns PNG bytes.
- ``render_video_frames(profile, events, output_dir, width, height, fps, duration) -> int``
  — render all frames for a video, returns frame count.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any

from utils.liquid_wire_timeline import visual_state
from utils.webgl_shaders import (
    FRAGMENT_SHADER,
    VERTEX_SHADER,
    family_to_shader_id,
)

log = logging.getLogger(__name__)

# HTML template injected into Chromium. The canvas is sized to the render
# resolution, WebGL2 context is created, shaders are compiled, and each
# frame is rendered by setting uniforms and calling toDataURL.
_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
canvas.width = {width};
canvas.height = {height};
const gl = canvas.getContext('webgl2', {{preserveDrawingBuffer: true}}) ||
           canvas.getContext('webgl', {{preserveDrawingBuffer: true}});
if (!gl) {{ document.title = 'NO_WEBGL'; }}

// Shaders
const vsSrc = `{vertex}`;
const fsSrc = `{fragment}`;

function compile(type, src) {{
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {{
        document.title = 'SHADER_ERROR: ' + gl.getShaderInfoLog(s);
        return null;
    }}
    return s;
}}

const vs = compile(gl.VERTEX_SHADER, vsSrc);
const fs = compile(gl.FRAGMENT_SHADER, fsSrc);
if (!vs || !fs) {{}}

const prog = gl.createProgram();
gl.attachShader(prog, vs);
gl.attachShader(prog, fs);
gl.linkProgram(prog);
if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {{
    document.title = 'LINK_ERROR: ' + gl.getProgramInfoLog(prog);
}}
gl.useProgram(prog);

// Full-screen quad.
const buf = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buf);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);
const posLoc = gl.getAttribLocation(prog, 'a_position');
gl.enableVertexAttribArray(posLoc);
gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

// Uniform locations.
const U = {{}};
const uniformNames = [
    'u_time','u_resolution','u_camera_pos','u_camera_target','u_fov',
    'u_light_pos','u_light_color','u_light_intensity',
    'u_base_color','u_accent_color','u_metalness','u_roughness',
    'u_bloom','u_compression','u_rupture','u_tide','u_stillness','u_family'
];
for (const name of uniformNames) {{
    U[name] = gl.getUniformLocation(prog, name);
}}

window.renderFrame = function(params) {{
    gl.uniform1f(U['u_time'], params.time);
    gl.uniform2f(U['u_resolution'], canvas.width, canvas.height);
    gl.uniform3fv(U['u_camera_pos'], params.camera_pos);
    gl.uniform3fv(U['u_camera_target'], params.camera_target);
    gl.uniform1f(U['u_fov'], params.fov);
    gl.uniform3fv(U['u_light_pos'], params.light_pos);
    gl.uniform3fv(U['u_light_color'], params.light_color);
    gl.uniform1f(U['u_light_intensity'], params.light_intensity);
    gl.uniform3fv(U['u_base_color'], params.base_color);
    gl.uniform3fv(U['u_accent_color'], params.accent_color);
    gl.uniform1f(U['u_metalness'], params.metalness);
    gl.uniform1f(U['u_roughness'], params.roughness);
    gl.uniform1f(U['u_bloom'], params.bloom);
    gl.uniform1f(U['u_compression'], params.compression);
    gl.uniform1f(U['u_rupture'], params.rupture);
    gl.uniform1f(U['u_tide'], params.tide);
    gl.uniform1f(U['u_stillness'], params.stillness);
    gl.uniform1i(U['u_family'], params.family_id);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    return canvas.toDataURL('image/png');
}};

document.title = 'READY';
</script>
</body>
</html>"""


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
    """HSV (0-1) to RGB (0-1) for shader uniforms."""
    import colorsys

    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (r, g, b)


def _event_state(t: float, events: list) -> dict[str, float]:
    """Extract visual event state at time t for shader uniforms."""
    state = visual_state(t, events)
    return {
        "bloom": float(state.get("bloom", 0.0)),
        "compression": float(state.get("compression", 0.0)),
        "rupture": float(state.get("rupture", 0.0)),
        "tide": float(state.get("tide", 0.0)),
        "stillness": float(state.get("stillness", 0.0)),
    }


def _camera_orbit(t: float, radius: float = 3.5) -> tuple[list[float], list[float]]:
    """Compute camera position and target for a slow orbital path."""
    angle = t * 0.15
    eye = [radius * math.cos(angle), 1.5 + 0.3 * math.sin(t * 0.1), radius * math.sin(angle)]
    target = [0.0, 0.0, 0.0]
    return eye, target


class WebGLRenderer:
    """Manages a headless Chromium browser for WebGL frame rendering.

    Parameters
    ----------
    width, height : int
        Render resolution (before supersampling).
    """

    def __init__(self, width: int = 1080, height: int = 1920) -> None:
        from playwright.sync_api import Browser, Page, Playwright

        self.width = int(width)
        self.height = int(height)
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._html_path: Path | None = None

    def _build_html(self) -> str:
        """Build the HTML page with shaders injected."""
        return _HTML_TEMPLATE.format(
            width=self.width,
            height=self.height,
            vertex=VERTEX_SHADER,
            fragment=FRAGMENT_SHADER,
        )

    def start(self) -> None:
        """Launch Chromium and load the WebGL page."""
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        assert self._pw is not None
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=[
                "--use-gl=swiftshader",
                "--enable-unsafe-swiftshader",
                "--ignore-gpu-blocklist",
                "--enable-webgl",
                "--webgl-software-rendering",
            ],
        )
        assert self._browser is not None
        self._page = self._browser.new_page(viewport={"width": self.width, "height": self.height})
        assert self._page is not None
        html = self._build_html()
        self._html_path = Path(os.environ.get("TEMP", "/tmp")) / "liquid_wire_webgl.html"
        self._html_path.write_text(html, encoding="utf-8")
        self._page.goto(f"file://{self._html_path}")
        self._page.wait_for_function("document.title === 'READY' || document.title.startsWith('ERROR')", timeout=15000)
        title = self._page.title()
        if title != "READY":
            raise RuntimeError(f"WebGL init failed: {title}")

    def render_frame(self, params: dict[str, Any]) -> bytes:
        """Render one frame and return PNG bytes.

        ``params`` must contain: time, camera_pos, camera_target, fov,
        light_pos, light_color, light_intensity, base_color, accent_color,
        metalness, roughness, bloom, compression, rupture, tide, stillness,
        family_id.
        """
        if self._page is None:
            raise RuntimeError("WebGLRenderer not started")
        data_url = self._page.evaluate("window.renderFrame", params)
        # data_url is "data:image/png;base64,...."
        import base64

        b64 = data_url.split(",", 1)[1]
        return base64.b64decode(b64)

    def render_video_frames(
        self,
        profile: dict,
        events: list,
        output_dir: Path,
        fps: int = 30,
        duration: float = 30.0,
    ) -> int:
        """Render all frames for a video. Returns the frame count."""
        output_dir.mkdir(parents=True, exist_ok=True)
        family = str(profile.get("family", "orb"))
        family_id = family_to_shader_id(family)
        palette = profile.get("palette", {})
        base_hue = float(palette.get("base_hue", 0.5))
        accent_hue = (base_hue + 0.3) % 1.0
        base_color = _hsv_to_rgb(base_hue, 0.8, 0.9)
        accent_color = _hsv_to_rgb(accent_hue, 0.7, 0.8)
        material = profile.get("material", {})
        metalness = float(material.get("metalness", 0.3))
        roughness = float(material.get("roughness", 0.4))
        frame_count = max(1, int(duration * fps))
        for i in range(frame_count):
            t = i / fps
            event_state = _event_state(t, events)
            eye, target = _camera_orbit(t)
            params = {
                "time": t,
                "camera_pos": eye,
                "camera_target": target,
                "fov": 1.2,
                "light_pos": [3.0, 4.0, 2.0],
                "light_color": [1.0, 0.95, 0.9],
                "light_intensity": 1.5,
                "base_color": list(base_color),
                "accent_color": list(accent_color),
                "metalness": metalness,
                "roughness": roughness,
                "bloom": event_state["bloom"],
                "compression": event_state["compression"],
                "rupture": event_state["rupture"],
                "tide": event_state["tide"],
                "stillness": event_state["stillness"],
                "family_id": family_id,
            }
            png_bytes = self.render_frame(params)
            frame_path = output_dir / f"frame_{i:05d}.png"
            frame_path.write_bytes(png_bytes)
        return frame_count

    def close(self) -> None:
        """Close the browser and cleanup."""
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()
        if self._html_path and self._html_path.exists():
            self._html_path.unlink(missing_ok=True)
        self._browser = None
        self._page = None
        self._pw = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()
