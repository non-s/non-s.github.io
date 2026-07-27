"""Testes unitários para a construção do comando FFmpeg da live."""
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

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
