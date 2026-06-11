import asyncio
import sys
import types


def test_text_to_speech_uses_coqui_fallback_when_edge_fails(monkeypatch, tmp_path):
    import generate_shorts

    class BrokenCommunicate:
        def __init__(self, *args, **kwargs):
            pass

        async def save(self, path):
            raise RuntimeError("edge unavailable")

    fake_edge = types.SimpleNamespace(Communicate=BrokenCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge)

    def fake_coqui(text, output_path, locale):
        output_path.write_bytes(b"fallback")
        return output_path

    monkeypatch.setattr(generate_shorts, "synthesize_with_coqui", fake_coqui)
    out = tmp_path / "voice.mp3"

    asyncio.run(generate_shorts.text_to_speech("hello", out, "en-US-AriaNeural"))

    assert out.read_bytes() == b"fallback"
