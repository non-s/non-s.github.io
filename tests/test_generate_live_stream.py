"""Testes unitários para a construção do comando FFmpeg da live."""
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import generate_pata_jazz_live as live


def _fake_popen(*_args, **_kwargs):
    proc = MagicMock()
    proc.poll.side_effect = [None, 0]
    proc.communicate.return_value = ("", "")
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
    curto escondia esses erros em falhas reais da live."""

    def _fake_proc(self, stderr: str):
        proc = MagicMock()
        proc.poll.side_effect = [None, 0]
        proc.communicate.return_value = ("", stderr)
        proc.returncode = 187
        return proc

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    def test_error_shaped_lines_are_surfaced(self, _mock_sleep, caplog):
        stderr = (
            "frame=  100 fps=30 q=23.0 size=512kB time=00:00:03.33\n"
            "[flv @ 0x1] Error muxing packet: Broken pipe\n"
            "frame=  101 fps=30 q=23.0 size=520kB time=00:00:03.36\n"
            + ("x" * 5000)
            + "\nConversion failed!\n"
        )
        proc = self._fake_proc(stderr)

        with caplog.at_level(logging.ERROR, logger="generate_pata_jazz_live"):
            code = live._wait_ffmpeg_stream(proc)

        assert code == 187
        assert any("Error muxing packet" in rec.message for rec in caplog.records)

    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    def test_no_error_keywords_does_not_crash(self, _mock_sleep, caplog):
        proc = self._fake_proc("frame=  1 fps=30 q=23.0 size=1kB time=00:00:00.03\n")

        code = live._wait_ffmpeg_stream(proc)

        assert code == 187
