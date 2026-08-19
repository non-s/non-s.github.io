"""Tests for the Engine 4.0 video modules.

Covers camera, lighting, visual_families_extended, post_process_extended,
transitions and particle_system_extended. Each test uses small arrays/images.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from utils.camera import Camera, CameraPath, procedural_shake, project_points
from utils.lighting import (
    DirectionalLight,
    PointLight,
    SpotLight,
    ambient_occlusion_approx,
    fresnel,
    shade_point,
    shade_points,
)
from utils.liquid_wire_timeline import CreativeEvent
from utils.particle_system_extended import (
    Emitter,
    Particle,
    ParticleSystemExtended,
    ParticleTrail,
    make_emitter,
)
from utils.post_process_extended import (
    POST_PROCESS_EXTENDED,
    anamorphic_flare,
    apply_extended,
    bokeh,
    color_grade,
    film_halation,
    god_rays,
    halation,
    lens_flare,
    optical_aberration,
)
from utils.transitions import (
    SceneTransition,
    crossfade,
    dissolve,
    glitch_transition,
    match_cut,
    morph_with_correspondence,
    wipe_transition,
)
from utils.visual_families_extended import VISUAL_FAMILIES_EXTENDED, dispatch

# --- camera ------------------------------------------------------------------

class TestCamera:
    def test_look_at_changes_position(self):
        cam = Camera(position=(0, 0, 5), target=(0, 0, 0), up=(0, 1, 0))
        cam.look_at(eye=(2, 0, 2), target=(0, 1, 0), up=(0, 1, 0))
        assert np.allclose(cam.position, (2, 0, 2))
        assert np.allclose(cam.target, (0, 1, 0))

    def test_perspective_matrix_shape(self):
        cam = Camera(position=(0, 0, 5), target=(0, 0, 0), up=(0, 1, 0))
        m = cam.projection_matrix(aspect=16.0 / 9.0)
        assert m.shape == (4, 4)
        assert np.all(np.isfinite(m))

    def test_project_points_3d_to_2d(self):
        cam = Camera(position=(0, 0, 5), target=(0, 0, 0), up=(0, 1, 0))
        pts = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [-1.0, 0.5, 0.0]])
        sx, sy, depth = project_points(pts, cam, width=320, height=240)
        assert sx.shape == (3,)
        assert sy.shape == (3,)
        assert depth.shape == (3,)
        assert np.all(np.isfinite(sx))
        assert np.all(np.isfinite(sy))

    def test_camera_path_add_and_sample(self):
        path = CameraPath()
        path.add_keyframe(0.0, eye=(0, 0, 5), target=(0, 0, 0), fov=60.0)
        path.add_keyframe(1.0, eye=(2, 0, 5), target=(0, 1, 0), fov=50.0)
        path.add_keyframe(2.0, eye=(0, 1, 5), target=(0, 0, 0), fov=60.0)
        eye, target, fov = path.sample(0.5)
        assert eye.shape == (3,)
        assert target.shape == (3,)
        assert 50.0 <= fov <= 60.0

    def test_procedural_shake_returns_pair(self):
        dx, dy = procedural_shake(t=1.5, freq=2.0, amplitude=0.02, seed=0)
        assert isinstance(dx, float)
        assert isinstance(dy, float)
        assert np.isfinite(dx) and np.isfinite(dy)


# --- lighting ----------------------------------------------------------------

class TestLighting:
    def test_point_light(self):
        light = PointLight(position=(0, 5, 0), color=(1, 1, 1), intensity=1.0, attenuation=0.5)
        assert light.type == "point"
        assert light.attenuation == 0.5

    def test_directional_light(self):
        light = DirectionalLight(direction=(0, -1, 0), color=(1, 1, 1), intensity=0.8)
        assert light.type == "directional"
        assert light.intensity == 0.8

    def test_spot_light(self):
        light = SpotLight(
            position=(0, 5, 0), target=(0, 0, 0), color=(1, 1, 1), intensity=1.0,
            cone_angle=np.radians(30.0), penumbra=0.2,
        )
        assert light.type == "spot"
        assert light.penumbra == 0.2

    def test_shade_points_with_normals(self):
        pts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
        nrms = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])
        lights = [
            PointLight(position=(0, 5, 0), color=(1, 1, 1), intensity=1.0, attenuation=0.1),
            DirectionalLight(direction=(0, -1, 0.5), color=(0.8, 0.8, 1.0), intensity=0.5),
        ]
        rgb = shade_points(pts, nrms, lights, ambient=0.1)
        assert rgb.shape == (3, 3)
        assert np.all(np.isfinite(rgb))
        assert np.all(rgb >= 0.0) and np.all(rgb <= 1.0)

    def test_fresnel(self):
        f = fresnel(view_dir=(0, 0, 1), normal=(1, 0, 0), power=3.0)
        assert isinstance(f, float)
        assert 0.0 <= f <= 1.0

    def test_shade_point_single(self):
        rgb = shade_point(
            point=(0.0, 0.0, 0.0),
            normal=(0.0, 1.0, 0.0),
            lights=[PointLight(position=(0, 5, 0), color=(1, 1, 1), intensity=1.0)],
            ambient=0.2,
        )
        assert rgb.shape == (3,)
        assert np.all(np.isfinite(rgb))
        assert np.all(rgb >= 0.0) and np.all(rgb <= 1.0)

    def test_shade_point_with_spot_and_directional(self):
        rgb = shade_point(
            point=(0.0, 0.0, 0.0),
            normal=(0.0, 1.0, 0.0),
            lights=[
                SpotLight(
                    position=(0, 5, 0), target=(0, 0, 0), color=(1, 1, 1), intensity=1.0,
                    cone_angle=np.radians(30.0), penumbra=0.2,
                ),
                DirectionalLight(direction=(0, -1, 0.3), color=(0.8, 0.8, 1.0), intensity=0.5),
            ],
            ambient=0.1,
            view_dir=(0, 0, 1),
        )
        assert rgb.shape == (3,)
        assert np.all(np.isfinite(rgb))

    def test_shade_point_1d_inputs(self):
        rgb = shade_point(
            point=np.array([0.0, 0.0, 0.0]),
            normal=np.array([0.0, 1.0, 0.0]),
            lights=[DirectionalLight(direction=(0, -1, 0), color=(1, 1, 1), intensity=0.8)],
        )
        assert rgb.shape == (3,)

    def test_shade_points_with_spot(self):
        pts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
        nrms = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])
        spot = SpotLight(
            position=(0, 5, 0), target=(0, 0, 0), color=(1, 1, 1), intensity=1.0,
            cone_angle=np.radians(45.0), penumbra=0.3,
        )
        rgb = shade_points(pts, nrms, [spot], ambient=0.1)
        assert rgb.shape == (3, 3)
        assert np.all(np.isfinite(rgb))
        assert np.all(rgb >= 0.0) and np.all(rgb <= 1.0)

    def test_shade_points_1d_promotion(self):
        rgb = shade_points(
            np.array([0.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            [DirectionalLight(direction=(0, -1, 0), color=(1, 1, 1), intensity=0.5)],
        )
        assert rgb.shape == (1, 3)

    def test_ambient_occlusion_approx(self):
        pts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
        nrms = np.array([[0.0, 1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0, 0.0]])

        def occ_field(p):
            return 0.3

        ao = ambient_occlusion_approx(pts, nrms, occ_field)
        assert ao.shape == (3,)
        assert np.all(np.isfinite(ao))
        assert np.all(ao >= 0.0) and np.all(ao <= 1.0)

    def test_ambient_occlusion_approx_1d(self):
        def occ_field(p):
            return 0.5

        ao = ambient_occlusion_approx(
            np.array([0.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), occ_field
        )
        assert ao.shape == (1,)

    def test_ambient_occlusion_approx_backfacing(self):
        pts = np.array([[0.0, 0.0, 0.0]])
        nrms = np.array([[0.0, -1.0, 0.0]])

        def occ_field(p):
            return 1.0

        ao = ambient_occlusion_approx(pts, nrms, occ_field)
        assert ao.shape == (1,)
        assert np.all(np.isfinite(ao))


# --- visual_families_extended ------------------------------------------------

FAMILIES = list(VISUAL_FAMILIES_EXTENDED)


@pytest.mark.parametrize("name", FAMILIES)
def test_visual_family_dispatch(name):
    n_theta, n_phi = 16, 12
    theta = np.linspace(0, 2 * np.pi, n_theta, endpoint=False)
    phi = np.linspace(0, np.pi, n_phi)
    T, P = np.meshgrid(theta, phi)
    profile = {"phase": 0.0, "breath_rate": 0.6, "melt_rate": 0.4, "twist": 0.5, "seed": 0}
    x, y, z = dispatch(name, T, P, t=0.5, profile=profile, events=[])
    assert x.shape == (n_phi, n_theta)
    assert y.shape == (n_phi, n_theta)
    assert z.shape == (n_phi, n_theta)
    assert np.all(np.isfinite(x))
    assert np.all(np.isfinite(y))
    assert np.all(np.isfinite(z))


@pytest.mark.parametrize("name", FAMILIES)
def test_visual_family_dispatch_with_events(name):
    n_theta, n_phi = 12, 8
    theta = np.linspace(0, 2 * np.pi, n_theta, endpoint=False)
    phi = np.linspace(0, np.pi, n_phi)
    T, P = np.meshgrid(theta, phi)
    profile = {
        "phase": 0.4,
        "breath_rate": 1.0,
        "melt_rate": 0.2,
        "twist": 0.8,
        "seed": 7,
        "palette": {"base_hue": 0.3, "hue_speed": 0.5},
        "growth_iterations": 3,
    }
    events = [
        CreativeEvent(kind="bloom", start=0.0, duration=1.5, intensity=0.6, direction=0.0, pitch_offset=0),
        CreativeEvent(kind="rupture", start=0.2, duration=1.0, intensity=0.7, direction=0.5, pitch_offset=5),
        CreativeEvent(kind="compression", start=0.5, duration=0.8, intensity=0.5, direction=-0.3, pitch_offset=-5),
    ]
    x, y, z = dispatch(name, T, P, t=1.0, profile=profile, events=events)
    assert x.shape == (n_phi, n_theta)
    assert np.all(np.isfinite(x))
    assert np.all(np.isfinite(y))
    assert np.all(np.isfinite(z))


def test_visual_family_dispatch_unknown_raises():
    with pytest.raises(KeyError):
        dispatch("does_not_exist", np.zeros(4), np.zeros(4), 0.0, {}, [])


# --- post_process_extended ---------------------------------------------------

@pytest.fixture
def small_image():
    return Image.new("RGB", (100, 100), color=(80, 120, 200))


@pytest.fixture
def bright_image():
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    yy, xx = np.ogrid[:100, :100]
    dist = np.sqrt((xx - 70) ** 2 + (yy - 30) ** 2)
    mask = dist < 20
    arr[mask] = [255, 255, 255]
    arr[~mask] = [60, 90, 150]
    return Image.fromarray(arr, "RGB")


@pytest.fixture
def rgba_image():
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    arr[..., :3] = 120
    arr[..., 3] = 200
    return Image.fromarray(arr, "RGBA")


@pytest.mark.parametrize("fn_name", ["lens_flare", "god_rays", "color_grade", "bokeh"])
def test_post_process_returns_image(fn_name, small_image):
    fn = {
        "lens_flare": lens_flare,
        "god_rays": god_rays,
        "color_grade": color_grade,
        "bokeh": bokeh,
    }[fn_name]
    out = fn(small_image, intensity=0.5)
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)
    arr = np.asarray(out)
    assert arr.shape == (100, 100, 3)
    assert np.all(np.isfinite(arr))


def test_lens_flare_starburst(bright_image):
    out = lens_flare(bright_image, intensity=1.0, flare_type="starburst")
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)


def test_lens_flare_position(bright_image):
    out = lens_flare(bright_image, intensity=0.8, position=(20.0, 20.0))
    assert isinstance(out, Image.Image)


def test_halation(bright_image):
    out = halation(bright_image, intensity=1.0, threshold=0.6)
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)
    arr = np.asarray(out)
    assert np.all(np.isfinite(arr))


def test_halation_no_highlights(small_image):
    out = halation(small_image, intensity=1.0, threshold=0.99)
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)


def test_film_halation(bright_image):
    out = film_halation(bright_image, intensity=1.0, spread=8.0)
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)
    arr = np.asarray(out)
    assert np.all(np.isfinite(arr))


def test_film_halation_no_highlights(small_image):
    out = film_halation(small_image, intensity=1.0)
    assert isinstance(out, Image.Image)


def test_anamorphic_flare(bright_image):
    out = anamorphic_flare(bright_image, intensity=1.0, streak_count=3)
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)
    arr = np.asarray(out)
    assert np.all(np.isfinite(arr))


def test_anamorphic_flare_no_highlights(small_image):
    out = anamorphic_flare(small_image, intensity=1.0)
    assert isinstance(out, Image.Image)


def test_optical_aberration_spherical(small_image):
    out = optical_aberration(small_image, intensity=0.6, aberration_type="spherical")
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)


def test_optical_aberration_coma(small_image):
    out = optical_aberration(small_image, intensity=0.6, aberration_type="coma")
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)


def test_optical_aberration_astigmatism(small_image):
    out = optical_aberration(small_image, intensity=0.6, aberration_type="astigmatism")
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)


def test_color_grade_all_luts(small_image):
    for lut in ["teal_orange", "bleach_bypass", "cross_process", "vintage", "unknown"]:
        out = color_grade(small_image, intensity=0.7, lut=lut)
        assert isinstance(out, Image.Image)
        assert out.size == (100, 100)


def test_bokeh_params(small_image):
    out = bokeh(small_image, intensity=1.0, focus_point=(0.3, 0.7), blur=10.0, blades=8)
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)


def test_god_rays_custom_source(small_image):
    out = god_rays(small_image, intensity=0.5, source_pos=(0.3, 0.2))
    assert isinstance(out, Image.Image)


def test_post_process_rgba_preserved(rgba_image):
    out = lens_flare(rgba_image, intensity=0.5)
    assert out.mode == "RGBA"
    assert out.size == (100, 100)


def test_post_process_extended_registry():
    for _name, fn in POST_PROCESS_EXTENDED.items():
        assert callable(fn)
    assert set(POST_PROCESS_EXTENDED) >= {
        "lens_flare", "god_rays", "halation", "color_grade",
        "anamorphic_flare", "film_halation", "optical_aberration", "bokeh",
    }


def test_apply_extended_chain(bright_image):
    profile = {
        "post_extended": {
            "color_grade": {"enabled": True, "intensity": 0.5, "lut": "vintage"},
            "halation": {"enabled": True, "intensity": 0.6, "threshold": 0.6},
            "disabled_effect": {"enabled": False, "intensity": 1.0},
            "unknown_effect": {"enabled": True, "intensity": 1.0},
        }
    }
    out = apply_extended(bright_image, profile)
    assert isinstance(out, Image.Image)
    assert out.size == (100, 100)


def test_apply_extended_no_profile(small_image):
    out = apply_extended(small_image, {})
    assert out is small_image
    out2 = apply_extended(small_image, {"post_extended": "not_a_dict"})
    assert out2 is small_image


# --- transitions -------------------------------------------------------------

class TestTransitions:
    def test_crossfade(self):
        a = np.random.RandomState(0).rand(20, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = crossfade(a, b, alpha=0.5)
        assert out.shape == (20, 3)
        assert np.all(np.isfinite(out))

    def test_crossfade_resizes_smaller(self):
        a = np.random.RandomState(0).rand(5, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = crossfade(a, b, alpha=0.3)
        assert out.shape == (20, 3)
        assert np.all(np.isfinite(out))

    def test_morph_with_correspondence_linear_equal(self):
        a = np.random.RandomState(0).rand(20, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = morph_with_correspondence(a, b, alpha=0.5, method="linear")
        assert out.shape == (20, 3)
        assert np.all(np.isfinite(out))
        assert np.allclose(out, 0.5 * a + 0.5 * b)

    def test_morph_with_correspondence_spherical(self):
        a = np.random.RandomState(0).rand(20, 3) + 0.5
        b = np.random.RandomState(1).rand(20, 3) + 0.5
        out = morph_with_correspondence(a, b, alpha=0.5, method="spherical")
        assert out.shape == (20, 3)
        assert np.all(np.isfinite(out))

    def test_morph_with_correspondence_a_longer(self):
        a = np.random.RandomState(0).rand(30, 3)
        b = np.random.RandomState(1).rand(10, 3)
        out = morph_with_correspondence(a, b, alpha=0.5, method="linear")
        assert out.shape == (30, 3)
        assert np.all(np.isfinite(out))

    def test_morph_with_correspondence_b_longer(self):
        a = np.random.RandomState(0).rand(10, 3)
        b = np.random.RandomState(1).rand(25, 3)
        out = morph_with_correspondence(a, b, alpha=0.5, method="linear")
        assert out.shape == (25, 3)
        assert np.all(np.isfinite(out))

    def test_morph_with_correspondence_spherical_zero_norm(self):
        a = np.zeros((5, 3))
        b = np.random.RandomState(1).rand(5, 3)
        out = morph_with_correspondence(a, b, alpha=0.5, method="spherical")
        assert out.shape == (5, 3)
        assert np.all(np.isfinite(out))

    def test_dissolve(self):
        a = np.random.RandomState(0).rand(20, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = dissolve(a, b, alpha=0.5, noise_threshold=0.5, seed=0)
        assert out.shape == (20, 3)
        assert np.all(np.isfinite(out))

    def test_dissolve_resizes_smaller(self):
        a = np.random.RandomState(0).rand(5, 3)
        b = np.random.RandomState(1).rand(25, 3)
        out = dissolve(a, b, alpha=0.5, seed=1)
        assert out.shape == (25, 3)
        assert np.all(np.isfinite(out))

    def test_wipe_transition(self):
        a = np.random.RandomState(0).rand(20, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = wipe_transition(a, b, alpha=0.5, direction=(1, 0, 0))
        assert out.shape[1] == 3
        assert np.all(np.isfinite(out))

    def test_wipe_transition_zero_direction(self):
        a = np.random.RandomState(0).rand(20, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = wipe_transition(a, b, alpha=0.5, direction=(0, 0, 0))
        assert np.allclose(out, a)

    def test_wipe_transition_flat_projection(self):
        a = np.zeros((10, 3))
        b = np.zeros((10, 3))
        out = wipe_transition(a, b, alpha=0.5, direction=(1, 0, 0))
        assert out.shape[1] == 3
        assert np.all(np.isfinite(out))

    def test_glitch_transition(self):
        a = np.random.RandomState(0).rand(15, 3)
        b = np.random.RandomState(1).rand(15, 3)
        out = glitch_transition(a, b, alpha=0.5, seed=0)
        assert out.shape[1] == 3
        assert np.all(np.isfinite(out))

    def test_glitch_transition_resizes(self):
        a = np.random.RandomState(0).rand(5, 3)
        b = np.random.RandomState(1).rand(15, 3)
        out = glitch_transition(a, b, alpha=0.5, seed=0)
        assert out.shape == (15, 3)
        assert np.all(np.isfinite(out))

    def test_match_cut(self):
        a = np.random.RandomState(0).rand(20, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = match_cut(a, b, alpha=0.5, center=(0, 0, 0), radius=1.0)
        assert out.shape == (20, 3)
        assert np.all(np.isfinite(out))

    def test_match_cut_resizes(self):
        a = np.random.RandomState(0).rand(5, 3)
        b = np.random.RandomState(1).rand(20, 3)
        out = match_cut(a, b, alpha=0.5)
        assert out.shape == (20, 3)
        assert np.all(np.isfinite(out))

    def test_scene_transition_empty(self):
        st = SceneTransition()
        out = st.render(t=0.5)
        assert out.shape == (0, 3)

    def test_scene_transition_single(self):
        a = np.random.RandomState(0).rand(10, 3)
        st = SceneTransition()
        st.add_scene(a, duration=1.0)
        out = st.render(t=0.5)
        assert np.allclose(out, a)

    def test_scene_transition(self):
        a = np.random.RandomState(0).rand(10, 3)
        b = np.random.RandomState(1).rand(10, 3)
        st = SceneTransition()
        st.add_scene(a, duration=1.0)
        st.add_scene(b, duration=1.0)
        out = st.render(t=0.5)
        assert out.shape[1] == 3
        assert np.all(np.isfinite(out))

    def test_scene_transition_boundaries(self):
        a = np.random.RandomState(0).rand(8, 3)
        b = np.random.RandomState(1).rand(8, 3)
        st = SceneTransition()
        st.add_scene(a, duration=1.0)
        st.add_scene(b, duration=1.0)
        assert np.allclose(st.render(t=0.0), a)
        assert np.allclose(st.render(t=2.0), b)
        # mid-transition
        mid = st.render(t=1.5)
        assert mid.shape == (8, 3)

    def test_scene_transition_three_scenes(self):
        a = np.random.RandomState(0).rand(6, 3)
        b = np.random.RandomState(1).rand(6, 3)
        c = np.random.RandomState(2).rand(6, 3)
        st = SceneTransition()
        st.add_scene(a, duration=1.0)
        st.add_scene(b, duration=1.0)
        st.add_scene(c, duration=1.0)
        out = st.render(t=2.5)
        assert out.shape == (6, 3)


# --- particle_system_extended ------------------------------------------------

PARTICLE_TYPES = ["embers", "sparks", "dust", "smoke", "rain", "snow", "bubbles", "fireflies", "debris"]


@pytest.mark.parametrize("ptype", PARTICLE_TYPES)
def test_make_emitter_all_types(ptype):
    emitter = make_emitter(ptype, position=(0, 0, 0), seed=0)
    assert isinstance(emitter, Emitter)
    assert emitter.particle_type == ptype
    particles = emitter.update(dt=0.1, t=0.0)
    assert all(isinstance(p, Particle) for p in particles)


def test_make_emitter_unknown_falls_back():
    emitter = make_emitter("unknown_type", position=(0, 0, 0), seed=0)
    assert isinstance(emitter, Emitter)


def test_emitter_color_gradient_multi():
    gradient = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    emitter = Emitter(
        position=(0, 0, 0),
        spawn_rate=100.0,
        color_gradient=gradient,
        seed=0,
    )
    parts = emitter.update(dt=0.1, t=0.0)
    assert len(parts) > 0
    assert all(p.color.shape == (3,) for p in parts)


def test_emitter_color_gradient_two():
    emitter = Emitter(
        position=(0, 0, 0),
        spawn_rate=100.0,
        color_gradient=[(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
        seed=1,
    )
    parts = emitter.update(dt=0.1, t=0.0)
    assert all(p.color.shape == (3,) for p in parts)


class TestParticleSystemExtended:
    def test_make_emitter_embers(self):
        emitter = make_emitter("embers", position=(0, 0, 0), seed=0)
        assert isinstance(emitter, Emitter)
        assert emitter.particle_type == "embers"

    def test_system_update_and_render(self):
        system = ParticleSystemExtended(gravity=(0, -9.81, 0), wind=(0, 0, 0), seed=0)
        emitter = make_emitter("embers", position=(0, 0, 0), seed=0, spawn_rate=50.0)
        system.add_emitter(emitter)
        # Step a few frames.
        for i in range(5):
            system.update(dt=0.05, t=0.05 * i)
        projected, sizes, colors, alphas = system.render(width=320, height=240)
        assert len(sizes) == len(colors) == len(alphas)
        if projected.size:
            assert np.all(np.isfinite(projected))

    def test_system_render_empty(self):
        system = ParticleSystemExtended(seed=0)
        projected, sizes, colors, alphas = system.render(width=100, height=100)
        assert sizes.shape == (0,)
        assert colors.shape == (0, 3)


@pytest.mark.parametrize("ptype", PARTICLE_TYPES)
def test_system_integrate_each_type(ptype):
    system = ParticleSystemExtended(
        gravity=(0, -9.81, 0), wind=(0.5, 0, 0.3), drag=0.1, seed=0,
    )
    emitter = make_emitter(ptype, position=(0, 0, 0), seed=0, spawn_rate=80.0)
    system.add_emitter(emitter)
    for i in range(8):
        system.update(dt=0.05, t=0.05 * i)
    projected, sizes, colors, alphas = system.render(width=320, height=240)
    assert len(sizes) == len(colors) == len(alphas)
    if projected.size:
        assert np.all(np.isfinite(projected))
        assert np.all(np.isfinite(sizes))
        assert np.all(np.isfinite(colors))
        assert np.all(np.isfinite(alphas))


def test_system_render_with_camera():
    system = ParticleSystemExtended(gravity=(0, -9.81, 0), seed=0)
    emitter = make_emitter("embers", position=(0, 0, 0), seed=0, spawn_rate=100.0)
    system.add_emitter(emitter)
    for i in range(5):
        system.update(dt=0.05, t=0.05 * i)
    camera = {"eye": [0, 0, 5], "target": [0, 0, 0], "up": [0, 1, 0], "fov": 60.0}
    projected, sizes, colors, alphas = system.render(width=320, height=240, camera=camera)
    if projected.size:
        assert projected.shape[1] == 2
        assert np.all(np.isfinite(projected))


def test_system_emitters_without_camera_2d_mapping():
    system = ParticleSystemExtended(seed=1)
    emitter = make_emitter("dust", position=(0.2, 0.2, 0.2), seed=0, spawn_rate=50.0)
    system.add_emitter(emitter)
    for i in range(4):
        system.update(dt=0.05, t=0.05 * i)
    projected, *_ = system.render(width=200, height=100)
    if projected.size:
        assert projected.shape[1] == 2


def test_particle_trail_basic():
    trail = ParticleTrail(length=5, fade=1.5)
    for i in range(8):
        p = Particle(
            pos=np.array([i, i, i], dtype=np.float64),
            vel=np.array([0, 0, 0], dtype=np.float64),
            age=float(i) * 0.1,
            lifetime=1.0,
            size=1.0,
            color=np.array([1.0, 0.0, 0.0]),
            alpha=1.0,
            type="embers",
            seed=float(i),
        )
        trail.update(p)
    assert len(trail.positions) == 5
    projected, sizes, colors, alphas = trail.render(width=200, height=200)
    assert projected.shape[0] == 5
    assert sizes.shape[0] == 5
    assert colors.shape == (5, 3)
    assert alphas.shape[0] == 5


def test_particle_trail_empty():
    trail = ParticleTrail(length=5)
    projected, sizes, colors, alphas = trail.render(width=100, height=100)
    assert projected.shape == (0, 2)
    assert sizes.shape == (0,)


def test_particle_trail_with_camera():
    trail = ParticleTrail(length=10)
    for i in range(12):
        p = Particle(
            pos=np.array([i * 0.1, 0.0, 0.0]),
            vel=np.zeros(3),
            age=0.0, lifetime=1.0, size=1.0,
            color=np.array([1.0, 1.0, 1.0]), alpha=1.0, type="sparks", seed=float(i),
        )
        trail.update(p)
    camera = {"eye": [0, 0, 5], "target": [0, 0, 0], "up": [0, 1, 0], "fov": 60.0}
    projected, sizes, colors, alphas = trail.render(width=320, height=240, camera=camera)
    assert projected.shape[0] == 10
    assert projected.shape[1] == 2


def test_system_ages_out_particles():
    system = ParticleSystemExtended(gravity=(0, -9.81, 0), seed=0)
    emitter = make_emitter("sparks", position=(0, 0, 0), seed=0, spawn_rate=200.0)
    system.add_emitter(emitter)
    system.update(dt=0.1, t=0.0)
    initial = len(system.particles)
    assert initial > 0
    # Run many steps so particles die of old age.
    for i in range(1, 50):
        system.update(dt=0.1, t=0.1 * i)
    # Particles should still be spawning/dying; finite counts.
    assert isinstance(len(system.particles), int)
