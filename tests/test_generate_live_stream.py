"""Testes unitários para a construção do comando FFmpeg da live."""
import json
import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import generate_pata_jazz_live as live


def _fake_popen(*_args, **_kwargs):
    proc = MagicMock()
    proc.poll.side_effect = [None, 0]
    proc.returncode = 0
    return proc


class TestRunFfmpegStreamCommand:
    """Garante que a URL de ingestao e o formato flv nunca sejam corrompidos."""

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_duration_flag_inserted_before_stream_url(self, mock_popen, _mock_sleep):
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"

        live._run_ffmpeg_stream(Path("loop.mp4"), stream_url, duration_minutes=350)

        cmd = mock_popen.call_args[0][0]
        assert cmd[-1] == stream_url
        assert cmd[-5:] == ["-f", "flv", "-t", "21000", stream_url]

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_no_duration_keeps_format_adjacent_to_url(self, mock_popen, _mock_sleep):
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"

        live._run_ffmpeg_stream(Path("loop.mp4"), stream_url, duration_minutes=0)

        cmd = mock_popen.call_args[0][0]
        assert cmd[-3:] == ["-f", "flv", stream_url]

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_video_input_uses_concat_demuxer_not_single_file(self, mock_popen, _mock_sleep):
        """O video de loop e um playlist concat lido com -stream_loop -1, nao
        um unico arquivo mp4 pre-renderizado (que exigia reabrir o arquivo
        inteiro a cada volta do loop, travando a live visivelmente)."""
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, duration_minutes=0)

        cmd = mock_popen.call_args[0][0]
        assert cmd[:10] == [
            "ffmpeg", "-re", "-fflags", "+genpts",
            "-stream_loop", "-1", "-f", "concat", "-safe", "0",
        ]
        assert cmd[10:12] == ["-i", "concat.txt"]

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_audio_input_is_also_read_in_real_time(self, mock_popen, _mock_sleep, tmp_path):
        """Sem -re no input de audio, o FFmpeg le/decodifica a playlist de
        audio o mais rapido possivel, disputando CPU com a codificacao de
        video em tempo real e derrubando a live (Broken pipe apos alguns
        minutos, com o encode ficando cada vez mais atras do tempo real)."""
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"
        audio_playlist = tmp_path / "audio.txt"
        audio_playlist.write_text("")

        live._start_ffmpeg_stream(
            Path("concat.txt"), stream_url, duration_minutes=0, audio_playlist=audio_playlist
        )

        cmd = mock_popen.call_args[0][0]
        expected_audio_block = ["-re", "-stream_loop", "-1", "-f", "concat", "-safe", "0", "-i", str(audio_playlist)]
        audio_value_index = cmd.index(str(audio_playlist))
        start = audio_value_index - (len(expected_audio_block) - 1)
        assert cmd[start:audio_value_index + 1] == expected_audio_block

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_uses_ultrafast_preset_for_cpu_headroom(self, mock_popen, _mock_sleep):
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, duration_minutes=0)

        cmd = mock_popen.call_args[0][0]
        preset_index = cmd.index("-preset")
        assert cmd[preset_index + 1] == "ultrafast"

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_720p_uses_lower_bitrate_than_1080p(self, mock_popen, _mock_sleep):
        """720p tem ~2.25x menos pixels por frame que 1080p; o bitrate deve
        cair junto para nao desperdicar banda/qualidade num frame menor
        (1080p30 com ultrafast ainda cai pra tras no runner de 2 vCPUs do
        GitHub Actions - reduzir a resolucao e o que da folga real de CPU)."""
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, duration_minutes=0, resolution=(1280, 720))
        cmd_720p = mock_popen.call_args[0][0]

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, duration_minutes=0, resolution=(1920, 1080))
        cmd_1080p = mock_popen.call_args[0][0]

        bitrate_720p = int(cmd_720p[cmd_720p.index("-b:v") + 1].rstrip("k"))
        bitrate_1080p = int(cmd_1080p[cmd_1080p.index("-b:v") + 1].rstrip("k"))
        assert bitrate_720p < bitrate_1080p
        # -bufsize deve ser 2x o -maxrate, dando folga a picos curtos sem
        # exigir sustentar o dobro do bitrate indefinidamente.
        maxrate_720p = int(cmd_720p[cmd_720p.index("-maxrate") + 1].rstrip("k"))
        bufsize_720p = int(cmd_720p[cmd_720p.index("-bufsize") + 1].rstrip("k"))
        assert bufsize_720p == maxrate_720p * 2


class TestAudioVisualizer:
    """Visualizer de áudio reativo (showcqt) na borda inferior da live.

    Opt-in via LIVE_VISUALIZER=1 — default OFF para não arriscar CPU no
    runner gratuito em produção. Os testes garantem que o caminho default
    (sem visualizador) não inclui o filtro, e que o caminho opt-in injeta
    o showcqt + overlay no canto inferior."""

    def test_default_off_does_not_include_showcqt(self, monkeypatch):
        monkeypatch.delenv("LIVE_VISUALIZER", raising=False)
        assert live._visualizer_enabled() is False
        assert "showcqt" not in live._build_overlay_filter((1280, 720), audio_input_index=1)
        assert "showcqt" not in live._build_overlay_filter((1280, 720), audio_input_index=None)

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_cmd_without_visualizer_has_no_showcqt(self, mock_popen, _mock_sleep, monkeypatch):
        monkeypatch.delenv("LIVE_VISUALIZER", raising=False)
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"
        audio_playlist = Path("audio.txt")

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, audio_playlist=audio_playlist)

        cmd = mock_popen.call_args[0][0]
        assert not any("showcqt" in str(arg) for arg in cmd)
        assert "-vf" in cmd
        assert "-filter_complex" not in cmd

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_cmd_with_visualizer_includes_showcqt_and_overlay(self, mock_popen, _mock_sleep, monkeypatch, tmp_path):
        monkeypatch.setenv("LIVE_VISUALIZER", "1")
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"
        audio_playlist = tmp_path / "audio.txt"
        audio_playlist.write_text("")

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, audio_playlist=audio_playlist)

        cmd = mock_popen.call_args[0][0]
        assert "-filter_complex" in cmd
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "showcqt" in fc
        assert "overlay=0:H-h" in fc
        # drawtext ainda presente (não pode sumir quando visualizer liga).
        assert "drawtext" in fc

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_cmd_with_visualizer_without_audio_falls_back_to_vf(self, mock_popen, _mock_sleep, monkeypatch):
        """Sem playlist de áudio não há como alimentar o showcqt — cai no
        caminho -vf simples mesmo com LIVE_VISUALIZER=1."""
        monkeypatch.setenv("LIVE_VISUALIZER", "1")
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, audio_playlist=None)

        cmd = mock_popen.call_args[0][0]
        assert "-vf" in cmd
        assert "-filter_complex" not in cmd
        assert not any("showcqt" in str(arg) for arg in cmd)

    def test_overlay_position_is_bottom_corner(self, monkeypatch):
        monkeypatch.setenv("LIVE_VISUALIZER", "1")
        fc = live._build_overlay_filter((1280, 720), audio_input_index=1)
        assert "overlay=0:H-h" in fc

    def test_visualizer_alpha_is_subtle(self, monkeypatch):
        monkeypatch.setenv("LIVE_VISUALIZER", "1")
        fc = live._build_overlay_filter((1280, 720), audio_input_index=1)
        # alpha 0.6 = colorchannelmixer=aa=0.6
        assert "colorchannelmixer=aa=0.6" in fc
        assert "size=1280x80" in fc


class TestVisualizerModes:
    """LIVE_VISUALIZER aceita showcqt (default, =1), showwaves e
    avectorscope. Cada modo gera o filtro FFmpeg correto."""

    def test_showcqt_is_default_and_equivalent_to_1(self, monkeypatch):
        monkeypatch.setenv("LIVE_VISUALIZER", "showcqt")
        assert live._visualizer_enabled() is True
        assert live._visualizer_mode() == "showcqt"
        fc = live._build_visualizer_filter_chain(1)
        assert "showcqt" in fc
        assert "timeclamp=0.5" in fc

        monkeypatch.setenv("LIVE_VISUALIZER", "1")
        assert live._visualizer_mode() == "showcqt"

    def test_showwaves_mode_uses_showwaves_filter(self, monkeypatch):
        monkeypatch.setenv("LIVE_VISUALIZER", "showwaves")
        assert live._visualizer_mode() == "showwaves"
        fc = live._build_visualizer_filter_chain(1)
        assert "showwaves" in fc
        assert "showcqt" not in fc

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_showwaves_cmd_includes_showwaves_filter(self, mock_popen, _mock_sleep, monkeypatch, tmp_path):
        monkeypatch.setenv("LIVE_VISUALIZER", "showwaves")
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"
        audio_playlist = tmp_path / "audio.txt"
        audio_playlist.write_text("")

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, audio_playlist=audio_playlist)

        cmd = mock_popen.call_args[0][0]
        assert "-filter_complex" in cmd
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "showwaves" in fc
        assert "showcqt" not in fc

    def test_avectorscope_mode_uses_avectorscope_filter(self, monkeypatch):
        monkeypatch.setenv("LIVE_VISUALIZER", "avectorscope")
        assert live._visualizer_mode() == "avectorscope"
        fc = live._build_visualizer_filter_chain(1)
        assert "avectorscope" in fc
        assert "showcqt" not in fc

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_avectorscope_cmd_includes_avectorscope_filter(self, mock_popen, _mock_sleep, monkeypatch, tmp_path):
        monkeypatch.setenv("LIVE_VISUALIZER", "avectorscope")
        mock_popen.side_effect = _fake_popen
        stream_url = "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl-mnop"
        audio_playlist = tmp_path / "audio.txt"
        audio_playlist.write_text("")

        live._start_ffmpeg_stream(Path("concat.txt"), stream_url, audio_playlist=audio_playlist)

        cmd = mock_popen.call_args[0][0]
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "avectorscope" in fc

    def test_unknown_mode_disables_visualizer(self, monkeypatch):
        monkeypatch.setenv("LIVE_VISUALIZER", "foobar")
        assert live._visualizer_mode() == ""
        assert live._visualizer_enabled() is False

    def test_empty_env_disables_visualizer(self, monkeypatch):
        monkeypatch.delenv("LIVE_VISUALIZER", raising=False)
        assert live._visualizer_mode() == ""
        assert live._visualizer_enabled() is False


class TestWaitFfmpegStreamErrorSurfacing:
    """A causa raiz de uma falha do FFmpeg costuma estar no meio do stderr,
    nao no final (que e so o resumo de estatisticas do libx264) - um tail
    curto escondia esses erros em falhas reais da live.

    Como o stderr agora e redirecionado para um arquivo de log (evitando
    deadlock de pipe), o teste grava o conteudo no arquivo esperado e
    valida que as linhas de erro sao extraidas dele.
    """

    def _fake_proc(self, stderr_tail: str):
        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.returncode = 187
        return proc

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.OUTPUT_DIR")
    def test_error_shaped_lines_are_surfaced(self, _mock_outdir, _mock_sleep, caplog, tmp_path):
        _mock_outdir.__truediv__ = lambda self, other: tmp_path / other
        stderr = (
            "frame=  100 fps=30 q=23.0 size=512kB time=00:00:03.33\n"
            "[flv @ 0x1] Error muxing packet: Broken pipe\n"
            "frame=  101 fps=30 q=23.0 size=520kB time=00:00:03.36\n"
            + ("x" * 5000)
            + "\nConversion failed!\n"
        )
        (tmp_path / "live_ffmpeg.log").write_text(stderr, encoding="utf-8")
        proc = self._fake_proc(stderr)

        with caplog.at_level(logging.ERROR, logger="generate_pata_jazz_live"):
            code = live._wait_ffmpeg_stream(proc)

        assert code == 187
        assert any("Error muxing packet" in rec.message for rec in caplog.records)

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.OUTPUT_DIR")
    def test_no_error_keywords_does_not_crash(self, _mock_outdir, _mock_sleep, caplog, tmp_path):
        _mock_outdir.__truediv__ = lambda self, other: tmp_path / other
        (tmp_path / "live_ffmpeg.log").write_text(
            "frame=  1 fps=30 q=23.0 size=1kB time=00:00:00.03\n", encoding="utf-8"
        )
        proc = self._fake_proc("")

        code = live._wait_ffmpeg_stream(proc)

        assert code == 187


class TestWaitFfmpegStreamWatchdog:
    """Confirmado em producao (run 30178358662): o FFmpeg pode travar - parar
    de progredir sem crashar e sem respeitar seu proprio -t - e ficar rodando
    ate o job inteiro bater o timeout duro do GitHub Actions, que forca
    SIGKILL antes do finally poder chamar transition('complete'). O watchdog
    de max_seconds precisa matar esse processo travado sozinho, sem depender
    do temporizador externo do GHA."""

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.OUTPUT_DIR")
    def test_hung_process_is_killed_after_max_seconds(self, _mock_outdir, _mock_sleep, tmp_path):
        _mock_outdir.__truediv__ = lambda self, other: tmp_path / other
        (tmp_path / "live_ffmpeg.log").write_text("frame=1\n", encoding="utf-8")

        proc = MagicMock()
        proc.poll.return_value = None  # nunca sai sozinho - travado.
        proc.returncode = -9  # kill() reaped: SIGKILL.

        fake_now = [0.0]

        def _advancing_time():
            fake_now[0] += 10
            return fake_now[0]

        with patch("generate_pata_jazz_live.time.time", side_effect=_advancing_time):
            code = live._wait_ffmpeg_stream(proc, max_seconds=60)

        proc.kill.assert_called_once()
        assert code == -9

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.OUTPUT_DIR")
    def test_process_exiting_before_max_seconds_is_not_killed(self, _mock_outdir, _mock_sleep, tmp_path):
        _mock_outdir.__truediv__ = lambda self, other: tmp_path / other
        (tmp_path / "live_ffmpeg.log").write_text("frame=1\n", encoding="utf-8")

        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.returncode = 0

        code = live._wait_ffmpeg_stream(proc, max_seconds=6000)

        proc.kill.assert_not_called()
        assert code == 0


class TestSaveLiveMeta:
    """_save_live_meta() precisa mesclar com o conteudo ja existente, nao
    sobrescrever - upload_youtube.create_live_stream() grava broadcast_id/
    stream_id/ingestion_url em live_state.json logo antes desta funcao ser
    chamada em run_live.py.main(); sobrescrever apagaria exatamente os
    campos que upload_youtube._try_resume_existing_broadcast precisa pra
    reaproveitar o broadcast na proxima sessao."""

    def test_creates_file_when_none_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)

        live._save_live_meta(title="t", stream_url="rtmp://x")

        data = _read_json(tmp_path / "live_state.json")
        assert data["title"] == "t"
        assert data["stream_url"] == "rtmp://x"
        assert "updated_at" in data

    def test_preserves_broadcast_id_written_by_create_live_stream(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)
        (tmp_path / "live_state.json").write_text(
            '{"broadcast_id": "b1", "stream_id": "s1", "ingestion_url": "rtmp://a.rtmp.youtube.com/live2/key"}',
            encoding="utf-8",
        )

        live._save_live_meta(title="Pata Jazz Live", stream_url="rtmp://a.rtmp.youtube.com/live2/key")

        data = _read_json(tmp_path / "live_state.json")
        assert data["broadcast_id"] == "b1"
        assert data["stream_id"] == "s1"
        assert data["title"] == "Pata Jazz Live"

    def test_new_call_overrides_same_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)
        (tmp_path / "live_state.json").write_text('{"title": "old"}', encoding="utf-8")

        live._save_live_meta(title="new")

        assert _read_json(tmp_path / "live_state.json")["title"] == "new"

    def test_corrupted_existing_file_does_not_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)
        (tmp_path / "live_state.json").write_text("not json", encoding="utf-8")

        live._save_live_meta(title="t")

        assert _read_json(tmp_path / "live_state.json")["title"] == "t"


def _read_json(path):
    import json
    return json.loads(path.read_text(encoding="utf-8"))


class TestSignalHandlers:
    def test_register_signal_handlers_sets_shutdown_false(self):
        live._register_signal_handlers()
        assert live._shutdown is False

    def test_handle_sigterm_sets_shutdown(self):
        live._handle_sigterm(signal.SIGTERM, None)
        assert live._shutdown is True
        live._shutdown = False  # reset


class TestLoadLiveTitle:
    def test_returns_default_when_no_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)
        assert live._load_live_title().startswith("Pata Jazz")

    def test_returns_title_from_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)
        (tmp_path / "live_state.json").write_text(
            json.dumps({"title": "Custom Live Title"}), encoding="utf-8"
        )
        assert live._load_live_title() == "Custom Live Title"

    def test_truncates_long_title(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)
        (tmp_path / "live_state.json").write_text(
            json.dumps({"title": "x" * 200}), encoding="utf-8"
        )
        assert len(live._load_live_title()) == 100

    def test_invalid_json_returns_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "LIVE_META_DIR", tmp_path)
        (tmp_path / "live_state.json").write_text("not json", encoding="utf-8")
        assert live._load_live_title().startswith("Pata Jazz")


class TestBuildAudioPlaylist:
    def test_empty_pool_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "audio_pool", lambda: [])
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        result, dur = live._build_audio_playlist("stem")
        assert result is None
        assert dur == 0.0

    def test_all_zero_durations_returns_none(self, tmp_path, monkeypatch):
        files = [tmp_path / "a.mp3", tmp_path / "b.mp3"]
        for f in files:
            f.write_bytes(b"x")
        monkeypatch.setattr(live, "audio_pool", lambda: files)
        monkeypatch.setattr(live, "get_video_duration", lambda p: 0.0)
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        result, dur = live._build_audio_playlist("stem")
        assert result is None
        assert dur == 0.0

    def test_builds_playlist_with_valid_files(self, tmp_path, monkeypatch):
        files = [tmp_path / "a.mp3", tmp_path / "b.mp3", tmp_path / "bad.mp3"]
        for f in files:
            f.write_bytes(b"x")

        def _dur(p):
            return 30.0 if "bad" not in str(p) else 0.0

        monkeypatch.setattr(live, "audio_pool", lambda: files)
        monkeypatch.setattr(live, "get_video_duration", _dur)
        monkeypatch.setattr(live, "build_concat_demuxer", lambda paths, out: None)
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(live, "random", MagicMock(shuffle=lambda x: None))
        result, dur = live._build_audio_playlist("stem")
        assert result == tmp_path / "stem_audio_playlist.txt"
        assert dur == 60.0


class TestBuildLoopingInput:
    def test_empty_pool_raises(self, monkeypatch):
        monkeypatch.setattr(live, "ensure_dirs", lambda: None)
        monkeypatch.setattr(live, "pool_stats", lambda: {"videos": 0, "audio": 0})
        with pytest.raises(RuntimeError, match="vazio"):
            live._build_looping_input("stem")

    def test_builds_concat(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "ensure_dirs", lambda: None)
        monkeypatch.setattr(live, "pool_stats", lambda: {"videos": 5, "audio": 5})
        monkeypatch.setattr(live, "random_scene", lambda: "cat")
        monkeypatch.setattr(live, "hook_for_scene", lambda s: ("hook", "🐱"))
        vids = [tmp_path / f"v{i}.mp4" for i in range(3)]
        for v in vids:
            v.write_bytes(b"x")
        monkeypatch.setattr(live, "pick_videos", lambda **k: vids)
        monkeypatch.setattr(live, "run_ffmpeg", lambda args, **k: MagicMock())
        monkeypatch.setattr(live, "build_concat_demuxer", lambda paths, out: None)
        monkeypatch.setattr(live, "_build_audio_playlist", lambda stem: (tmp_path / "audio.txt", 100.0))
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        concat, audio = live._build_looping_input("stem")
        assert concat == tmp_path / "stem_concat.txt"
        assert audio == tmp_path / "audio.txt"


class TestTerminateFfmpegStream:
    def test_terminate_then_wait(self):
        proc = MagicMock()
        proc.wait.return_value = 0
        live._terminate_ffmpeg_stream(proc)
        proc.terminate.assert_called_once()

    def test_terminate_kills_on_timeout(self):
        import subprocess
        proc = MagicMock()
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15)
        live._terminate_ffmpeg_stream(proc)
        proc.kill.assert_called_once()

    def test_closes_log_handle(self):
        proc = MagicMock()
        log_handle = MagicMock()
        proc._log_handle = log_handle
        proc.wait.return_value = 0
        live._terminate_ffmpeg_stream(proc)
        log_handle.close.assert_called_once()


class TestWaitFfmpegStreamShutdown:
    def test_shutdown_flag_terminates_proc(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        (tmp_path / "live_ffmpeg.log").write_text("frame=1\n", encoding="utf-8")
        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.wait.return_value = 0
        proc.returncode = 0
        monkeypatch.setattr(live.time, "sleep", lambda s: None)
        monkeypatch.setattr(live, "_shutdown", True)
        code = live._wait_ffmpeg_stream(proc)
        proc.terminate.assert_called_once()
        assert code == 0
        live._shutdown = False

    def test_shutdown_kill_on_terminate_timeout(self, tmp_path, monkeypatch):
        import subprocess
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        (tmp_path / "live_ffmpeg.log").write_text("frame=1\n", encoding="utf-8")
        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30), 0]
        monkeypatch.setattr(live.time, "sleep", lambda s: None)
        monkeypatch.setattr(live, "_shutdown", True)
        live._wait_ffmpeg_stream(proc)
        proc.kill.assert_called_once()
        live._shutdown = False

    def test_stalled_progress_kills_proc(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        (tmp_path / "live_ffmpeg.log").write_text("frame=1\n", encoding="utf-8")
        progress = tmp_path / "progress.txt"
        progress.write_text("", encoding="utf-8")
        # mtime antiga -> idle_seconds > _STALL_GRACE_SECONDS
        import os
        old_mtime = time.time() - (live._STALL_GRACE_SECONDS + 100)
        os.utime(progress, (old_mtime, old_mtime))

        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.returncode = -9
        proc._progress_path = progress
        monkeypatch.setattr(live.time, "sleep", lambda s: None)
        monkeypatch.setattr(live, "_shutdown", False)
        code = live._wait_ffmpeg_stream(proc)
        proc.kill.assert_called_once()
        assert code == -9

    def test_progress_path_as_mock_treated_as_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        (tmp_path / "live_ffmpeg.log").write_text("frame=1\n", encoding="utf-8")
        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.returncode = 0
        # _progress_path auto-criado como MagicMock pelo getattr -> deve ser tratado como None
        proc._progress_path = MagicMock()
        monkeypatch.setattr(live.time, "sleep", lambda s: None)
        monkeypatch.setattr(live, "_shutdown", False)
        code = live._wait_ffmpeg_stream(proc)
        assert code == 0

    def test_exception_terminates_proc(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live, "OUTPUT_DIR", tmp_path)
        (tmp_path / "live_ffmpeg.log").write_text("frame=1\n", encoding="utf-8")
        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.wait.return_value = 0
        # Força exceção dentro do loop via _shutdown acessando propriedade que levanta
        monkeypatch.setattr(live.time, "sleep", lambda s: None)
        monkeypatch.setattr(live, "_shutdown", False)

        # Faz proc.poll levantar excecao na 1a chamada para cair no except
        call_count = {"n": 0}

        def _poll():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("boom")
            return 0

        proc.poll.side_effect = _poll
        live._wait_ffmpeg_stream(proc)
        proc.terminate.assert_called_once()


class TestMain:
    def test_no_stream_url_returns_1(self, monkeypatch):
        monkeypatch.setattr(live, "configure_logging", lambda: None)
        monkeypatch.setattr("sys.argv", ["generate_pata_jazz_live.py"])
        assert live.main() == 1

    def test_invalid_resolution_returns_1(self, monkeypatch):
        monkeypatch.setattr(live, "configure_logging", lambda: None)
        monkeypatch.setattr("sys.argv", ["x", "--stream-url", "rtmp://x", "--resolution", "abc"])
        assert live.main() == 1

    def test_invalid_duration_returns_1(self, monkeypatch):
        monkeypatch.setattr(live, "configure_logging", lambda: None)
        monkeypatch.setattr("sys.argv", ["x", "--stream-url", "rtmp://x", "--resolution", "1280x720",
                                          "--duration", "999"])
        assert live.main() == 1

    def test_build_loop_failure_returns_1(self, monkeypatch):
        monkeypatch.setattr(live, "configure_logging", lambda: None)
        monkeypatch.setattr("sys.argv", ["x", "--stream-url", "rtmp://x", "--resolution", "1280x720"])
        monkeypatch.setattr(live, "_register_signal_handlers", lambda: None)
        monkeypatch.setattr(live, "_build_looping_input",
                            MagicMock(side_effect=RuntimeError("boom")))
        monkeypatch.setattr(live, "log_exception_to_file", lambda *a, **k: None)
        assert live.main() == 1

    def test_normal_path_returns_zero_code(self, monkeypatch, tmp_path):
        monkeypatch.setattr(live, "configure_logging", lambda: None)
        monkeypatch.setattr("sys.argv", ["x", "--stream-url", "rtmp://x", "--resolution", "1280x720"])
        monkeypatch.setattr(live, "_register_signal_handlers", lambda: None)
        monkeypatch.setattr(live, "_build_looping_input",
                            lambda *a, **k: (tmp_path / "loop.txt", tmp_path / "audio.txt"))
        monkeypatch.setattr(live, "_load_live_title", lambda: "Title")
        monkeypatch.setattr(live, "_save_live_meta", lambda **k: None)
        monkeypatch.setattr(live, "_run_ffmpeg_stream", lambda *a, **k: 0)
        assert live.main() == 0

    def test_1920_downgraded_to_720(self, monkeypatch, tmp_path):
        captured = {}

        def _build(stem, target_resolution=(0, 0), **k):
            captured["res"] = target_resolution
            return (tmp_path / "loop.txt", tmp_path / "audio.txt")

        monkeypatch.setattr(live, "configure_logging", lambda: None)
        monkeypatch.setattr("sys.argv", ["x", "--stream-url", "rtmp://x", "--resolution", "1920x1080"])
        monkeypatch.setattr(live, "_register_signal_handlers", lambda: None)
        monkeypatch.setattr(live, "_build_looping_input", _build)
        monkeypatch.setattr(live, "_load_live_title", lambda: "Title")
        monkeypatch.setattr(live, "_save_live_meta", lambda **k: None)
        monkeypatch.setattr(live, "_run_ffmpeg_stream", lambda *a, **k: 0)
        live.main()
        assert captured["res"] == (1280, 720)

    def test_sigterm_returncode_treated_as_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(live, "configure_logging", lambda: None)
        monkeypatch.setattr("sys.argv", ["x", "--stream-url", "rtmp://x", "--resolution", "1280x720"])
        monkeypatch.setattr(live, "_register_signal_handlers", lambda: None)
        monkeypatch.setattr(live, "_build_looping_input",
                            lambda *a, **k: (tmp_path / "loop.txt", tmp_path / "audio.txt"))
        monkeypatch.setattr(live, "_load_live_title", lambda: "Title")
        monkeypatch.setattr(live, "_save_live_meta", lambda **k: None)
        monkeypatch.setattr(live, "_run_ffmpeg_stream", lambda *a, **k: -15)
        assert live.main() == 0


@pytest.mark.integration
class TestFFTVisualizerReal:
    """Testa os filtros de visualizador de audio (showcqt, showwaves,
    avectorscope) com FFmpeg real contra um tom senoidal de 1s.

    Skipped por padrao: so roda com `pytest -m integration` explicito E
    a env var RUN_FFMPEG_TESTS setada (evita gastar tempo/IO na suíte
    default). Tambem skip se o ffmpeg nao estiver no PATH.
    """

    @pytest.fixture(autouse=True)
    def _require_ffmpeg_env(self):
        if not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg nao encontrado no PATH")
        if not os.environ.get("RUN_FFMPEG_TESTS"):
            pytest.skip("RUN_FFMPEG_TESTS nao setada: teste de FFmpeg real pulado")

    def _run_visualizer(self, tmp_path, visualizer_filter):
        """Gera um tom senoidal de 1s e aplica um filtro de visualizador,
        escrevendo em um arquivo de saida (frame unico, sem stream RTMP)."""
        out = tmp_path / f"viz_{visualizer_filter}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
            "-filter_complex", f"[0:a]{visualizer_filter}=size=320x80[v];[1:v][v]overlay=0:H-h",
            "-t", "1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=5)
        assert proc.returncode == 0, (
            f"FFmpeg falhou para {visualizer_filter} (rc={proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')[-500:]}"
        )
        assert out.exists() and out.stat().st_size > 0
        out.unlink(missing_ok=True)

    def test_showcqt_visualizer(self, tmp_path):
        self._run_visualizer(tmp_path, "showcqt")

    def test_showwaves_visualizer(self, tmp_path):
        self._run_visualizer(tmp_path, "showwaves")

    def test_avectorscope_visualizer(self, tmp_path):
        self._run_visualizer(tmp_path, "avectorscope")
