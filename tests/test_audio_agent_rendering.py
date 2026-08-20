from generate_liquid_wire_video import _notes_for_role
from utils.liquid_wire_composer import NoteEvent


def test_role_renderer_includes_agent_descendants_only_for_its_voice():
    notes = [
        NoteEvent(60, 0, 1, .5, "motif"),
        NoteEvent(64, 1, 1, .4, "motif:organism-1"),
        NoteEvent(48, 0, 1, .5, "bass:organism-2"),
    ]
    selected = _notes_for_role(notes, "lead")
    assert [note.voice for note in selected] == ["motif", "motif:organism-1"]
