"""Testes para utils/log_config.py."""

from __future__ import annotations

import logging

import utils.log_config as log_config


class TestConfigureLogging:
    def test_adds_handler_when_root_has_none(self):
        root = logging.getLogger()
        saved_handlers = root.handlers[:]
        saved_level = root.level
        root.handlers = []
        try:
            log_config.configure_logging(level=logging.DEBUG)
            assert root.handlers
            assert root.level == logging.DEBUG
        finally:
            root.handlers = saved_handlers
            root.setLevel(saved_level)

    def test_idempotent_does_not_duplicate_handlers(self):
        root = logging.getLogger()
        saved_handlers = root.handlers[:]
        saved_level = root.level
        root.handlers = []
        try:
            log_config.configure_logging()
            log_config.configure_logging()
            log_config.configure_logging()
            assert len(root.handlers) == 1
        finally:
            root.handlers = saved_handlers
            root.setLevel(saved_level)

    def test_second_call_only_adjusts_level(self):
        root = logging.getLogger()
        saved_handlers = root.handlers[:]
        saved_level = root.level
        root.handlers = []
        try:
            log_config.configure_logging(level=logging.INFO)
            log_config.configure_logging(level=logging.WARNING)
            assert root.level == logging.WARNING
            assert len(root.handlers) == 1
        finally:
            root.handlers = saved_handlers
            root.setLevel(saved_level)

    def test_quiets_noisy_third_party_loggers(self):
        log_config.configure_logging()
        for name in ("urllib3", "requests", "googleapiclient"):
            assert logging.getLogger(name).level == logging.WARNING


class TestLogExceptionToFile:
    def test_creates_file_with_traceback(self, tmp_path):
        try:
            raise ValueError("boom")
        except ValueError as exc:
            path = log_config.log_exception_to_file(exc, tmp_path)

        assert path == tmp_path / "last_error.txt"
        content = path.read_text(encoding="utf-8")
        assert "ValueError" in content
        assert "boom" in content

    def test_appends_instead_of_overwriting(self, tmp_path):
        try:
            raise RuntimeError("first")
        except RuntimeError as exc:
            log_config.log_exception_to_file(exc, tmp_path)
        try:
            raise RuntimeError("second")
        except RuntimeError as exc:
            path = log_config.log_exception_to_file(exc, tmp_path)

        content = path.read_text(encoding="utf-8")
        assert "first" in content
        assert "second" in content

    def test_uses_custom_name(self, tmp_path):
        try:
            raise ValueError("custom")
        except ValueError as exc:
            path = log_config.log_exception_to_file(exc, tmp_path, name="custom_error.txt")

        assert path == tmp_path / "custom_error.txt"
        assert path.exists()

    def test_creates_output_dir_if_missing(self, tmp_path):
        output_dir = tmp_path / "nested" / "dir"
        try:
            raise ValueError("nested")
        except ValueError as exc:
            path = log_config.log_exception_to_file(exc, output_dir)

        assert path.exists()

    def test_includes_timestamp_marker(self, tmp_path):
        try:
            raise ValueError("timed")
        except ValueError as exc:
            path = log_config.log_exception_to_file(exc, tmp_path)

        content = path.read_text(encoding="utf-8")
        assert "=== " in content
        assert "UTC ===" in content
