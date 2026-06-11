from utils.experiments import AXES, assign_all_for_production


def test_music_bed_axis_is_registered():
    axes = {axis.name: axis for axis in AXES}

    assert axes["music_bed"].variants == ("off", "light_bed")


def test_assign_all_for_production_includes_music_bed():
    assignments = assign_all_for_production("story-123")

    assert assignments["music_bed"] in {"off", "light_bed"}
