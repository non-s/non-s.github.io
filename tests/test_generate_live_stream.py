"""Testes unitários para a construção do comando FFmpeg da live."""
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
