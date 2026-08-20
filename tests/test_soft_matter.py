import numpy as np

from utils.soft_matter import bridge_strands, interaction_deform, jelly_deform


def test_jelly_is_deterministic_and_deforms_without_shape_loss():
    sx, sy = np.meshgrid(np.linspace(10, 90, 8), np.linspace(20, 80, 6))
    ax, ay = jelly_deform(sx, sy, (50, 50), 1.2, .7)
    bx, by = jelly_deform(sx, sy, (50, 50), 1.2, .7)
    assert ax.shape == sx.shape == ay.shape
    assert np.array_equal(ax, bx) and np.array_equal(ay, by)
    assert not np.array_equal(ax, sx)


def test_fusion_pulls_skin_toward_other_organism():
    sx = np.full((3, 3), 20.0)
    sy = np.full((3, 3), 50.0)
    out_x, _ = interaction_deform(sx, sy, (100, 50), "fusion", 1, 0, 0, 100)
    assert np.all(out_x > sx)
    assert np.all(out_x < 100)


def test_bridge_is_multi_strand_continuous_wireframe():
    relation = {"strength": .8, "phase": 1.1}
    bridges = bridge_strands((10, 20), (110, 80), relation, 2.0)
    assert len(bridges) == 7
    assert all(len(strand) == 25 for strand in bridges)
    assert all(strand[0][0] != strand[-1][0] for strand in bridges)
