"""Testes para utils/tiktok_uploader.py — cobre a lógica de estado/decisão
do upload via Playwright sem depender de rede real ou credenciais do
TikTok (roda 100% headless/mockado em CI)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import utils.tiktok_uploader as tiktok_uploader


class TestHashtagsForTiktok:
    def test_uses_native_tiktok_hashtags_for_cat_scene(self):
        hashtags = tiktok_uploader._hashtags_for_tiktok({"scene": "sleepy cat", "mood": "relax"})
        assert "#catsoftiktok" in hashtags
        assert "#fyp" in hashtags

    def test_uses_native_tiktok_hashtags_for_dog_scene(self):
        hashtags = tiktok_uploader._hashtags_for_tiktok({"scene": "playful dog", "mood": "diversao"})
        assert "#dogsoftiktok" in hashtags

    def test_falls_back_to_meta_hashtags_on_generation_failure(self, monkeypatch):
        import utils.seo_keywords as seo_keywords

        def _boom(**k):
            raise RuntimeError("x")

        monkeypatch.setattr(seo_keywords, "generate_tiktok_hashtags", _boom)

        hashtags = tiktok_uploader._hashtags_for_tiktok({"scene": "cat", "hashtags": ["#PataJazz", "#Cats"]})

        assert hashtags == ["#PataJazz", "#Cats"]

    def test_missing_scene_and_mood_still_returns_hashtags(self):
        hashtags = tiktok_uploader._hashtags_for_tiktok({})
        assert len(hashtags) > 0


class TestRecordTiktokPost:
    def test_appends_record_with_expected_fields(self, tmp_path, monkeypatch):
        import utils.paths as paths
        monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)

        tiktok_uploader._record_tiktok_post("v.mp4", "Cute Cat", "https://tiktok.com/@x/video/1")

        posts = json.loads((tmp_path / "tiktok_posts.json").read_text(encoding="utf-8"))
        assert len(posts) == 1
        assert posts[0]["video"] == "v.mp4"
        assert posts[0]["title"] == "Cute Cat"
        assert posts[0]["url"] == "https://tiktok.com/@x/video/1"
        assert "posted_at" in posts[0]

    def test_appends_to_existing_list(self, tmp_path, monkeypatch):
        import utils.paths as paths
        monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
        (tmp_path / "tiktok_posts.json").write_text(
            json.dumps([{"video": "old.mp4", "title": "Old", "url": "u", "posted_at": "t"}]),
            encoding="utf-8",
        )

        tiktok_uploader._record_tiktok_post("new.mp4", "New", "https://tiktok.com/@x/video/2")

        posts = json.loads((tmp_path / "tiktok_posts.json").read_text(encoding="utf-8"))
        assert len(posts) == 2
        assert posts[-1]["video"] == "new.mp4"

    def test_caps_at_max_entries(self, tmp_path, monkeypatch):
        import utils.paths as paths
        monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
        old_posts = [{"video": f"v{i}.mp4", "title": "T", "url": "u", "posted_at": "t"}
                     for i in range(tiktok_uploader._MAX_TIKTOK_POSTS)]
        (tmp_path / "tiktok_posts.json").write_text(json.dumps(old_posts), encoding="utf-8")

        tiktok_uploader._record_tiktok_post("newest.mp4", "Newest", "u2")

        posts = json.loads((tmp_path / "tiktok_posts.json").read_text(encoding="utf-8"))
        assert len(posts) == tiktok_uploader._MAX_TIKTOK_POSTS
        assert posts[-1]["video"] == "newest.mp4"
        assert posts[0]["video"] == "v1.mp4"  # v0 foi descartado

    def test_recovers_from_corrupted_existing_file(self, tmp_path, monkeypatch):
        import utils.paths as paths
        monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
        (tmp_path / "tiktok_posts.json").write_text("not json", encoding="utf-8")

        tiktok_uploader._record_tiktok_post("v.mp4", "T", "u")  # nao deve levantar

        posts = json.loads((tmp_path / "tiktok_posts.json").read_text(encoding="utf-8"))
        assert len(posts) == 1

    def test_does_not_raise_on_write_failure(self, tmp_path, monkeypatch):
        import utils.paths as paths
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        monkeypatch.setattr(paths, "data_dir", lambda: blocker / "sub")

        tiktok_uploader._record_tiktok_post("v.mp4", "T", "u")  # nao deve levantar


class TestPageMentionsAny:
    def test_finds_marker_case_insensitive(self):
        page = MagicMock()
        page.inner_text.return_value = "Please VERIFY to continue"
        assert tiktok_uploader._page_mentions_any(page, ("verify to continue",)) == "verify to continue"

    def test_returns_none_when_absent(self):
        page = MagicMock()
        page.inner_text.return_value = "everything is fine"
        assert tiktok_uploader._page_mentions_any(page, ("captcha",)) is None

    def test_returns_none_on_exception(self):
        page = MagicMock()
        page.inner_text.side_effect = RuntimeError("page not ready")
        assert tiktok_uploader._page_mentions_any(page, ("captcha",)) is None


class TestWriteUploadState:
    def test_writes_json_with_stage_and_detail(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(tiktok_uploader, "_UPLOAD_STATE_FILE", state_file)

        tiktok_uploader._write_upload_state("video.mp4", "uploading_file", "some detail")

        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["video"] == "video.mp4"
        assert data["stage"] == "uploading_file"
        assert data["detail"] == "some detail"
        assert "at" in data

    def test_does_not_raise_when_write_fails(self, tmp_path, monkeypatch):
        # Diretorio pai que nao pode ser criado (arquivo no lugar de diretorio).
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        monkeypatch.setattr(tiktok_uploader, "_UPLOAD_STATE_FILE", blocker / "sub" / "state.json")
        tiktok_uploader._write_upload_state("v.mp4", "stage")  # nao deve levantar


class TestIsLoggedIn:
    def test_true_when_avatar_present_and_not_login_url(self):
        page = MagicMock()
        page.url = "https://www.tiktok.com/upload"
        page.query_selector.return_value = MagicMock()
        assert tiktok_uploader._is_logged_in(page) is True

    def test_false_when_on_login_url(self):
        page = MagicMock()
        page.url = "https://www.tiktok.com/login/phone-or-email/email"
        assert tiktok_uploader._is_logged_in(page) is False

    def test_false_when_no_avatar(self):
        page = MagicMock()
        page.url = "https://www.tiktok.com/upload"
        page.query_selector.return_value = None
        assert tiktok_uploader._is_logged_in(page) is False


class TestDoLogin:
    def _page(self, url_sequence, body_text="", has_email_input=True, has_pass_input=True):
        page = MagicMock()
        state = {"idx": 0}
        page.url = url_sequence[0]

        def _query_selector(selector):
            if "username" in selector:
                return MagicMock() if has_email_input else None
            if "password" in selector:
                return MagicMock() if has_pass_input else None
            return MagicMock()

        page.query_selector.side_effect = _query_selector
        page.inner_text.return_value = body_text

        def _advance_url(*a, **k):
            if state["idx"] + 1 < len(url_sequence):
                state["idx"] += 1
            page.url = url_sequence[state["idx"]]

        page.keyboard.press.side_effect = _advance_url
        return page

    def test_detects_captcha_before_filling_fields(self, monkeypatch):
        page = MagicMock()
        page.url = "https://www.tiktok.com/login/phone-or-email/email"
        page.inner_text.return_value = "Please verify to continue"
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)

        result = tiktok_uploader._do_login(page, "a@b.com", "pw")

        assert result is False
        page.query_selector.assert_not_called()

    def test_missing_email_field_fails(self, monkeypatch):
        page = self._page(["https://www.tiktok.com/login/phone-or-email/email"], has_email_input=False)
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        assert tiktok_uploader._do_login(page, "a@b.com", "pw") is False

    def test_missing_password_field_fails(self, monkeypatch):
        page = self._page(["https://www.tiktok.com/login/phone-or-email/email"], has_pass_input=False)
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        assert tiktok_uploader._do_login(page, "a@b.com", "pw") is False

    def test_successful_login_when_url_leaves_login(self, monkeypatch):
        page = self._page([
            "https://www.tiktok.com/login/phone-or-email/email",
            "https://www.tiktok.com/upload",
        ])
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        assert tiktok_uploader._do_login(page, "a@b.com", "pw") is True

    def test_incorrect_credentials_detected(self, monkeypatch):
        page = self._page(
            ["https://www.tiktok.com/login/phone-or-email/email"] * 2,
            body_text="Incorrect email or password",
        )
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        assert tiktok_uploader._do_login(page, "a@b.com", "pw") is False

    def test_rate_limited_detected(self, monkeypatch):
        page = self._page(
            ["https://www.tiktok.com/login/phone-or-email/email"] * 2,
            body_text="Maximum number of attempts reached",
        )
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        assert tiktok_uploader._do_login(page, "a@b.com", "pw") is False

    def test_captcha_detected_mid_login(self, monkeypatch):
        page = self._page(
            ["https://www.tiktok.com/login/phone-or-email/email"] * 2,
            body_text="Drag the slider to verify",
        )
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        assert tiktok_uploader._do_login(page, "a@b.com", "pw") is False

    def test_times_out_after_30_attempts(self, monkeypatch):
        page = self._page(["https://www.tiktok.com/login/phone-or-email/email"] * 40, body_text="")
        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        assert tiktok_uploader._do_login(page, "a@b.com", "pw") is False


class TestEnsureLogin:
    def test_returns_true_without_login_when_already_logged_in(self):
        page = MagicMock()
        with patch("utils.tiktok_uploader._is_logged_in", return_value=True), \
             patch("utils.tiktok_uploader._do_login") as mock_login:
            result = tiktok_uploader._ensure_login(page, MagicMock(), "a@b.com", "pw", Path("state.json"))
        assert result is True
        mock_login.assert_not_called()

    def test_falls_back_to_login_and_saves_session(self, tmp_path):
        page = MagicMock()
        context = MagicMock()
        state_path = tmp_path / "state.json"
        with patch("utils.tiktok_uploader._is_logged_in", return_value=False), \
             patch("utils.tiktok_uploader._do_login", return_value=True):
            result = tiktok_uploader._ensure_login(page, context, "a@b.com", "pw", state_path)
        assert result is True
        context.storage_state.assert_called_once_with(path=str(state_path))

    def test_login_failure_propagates(self, tmp_path):
        page = MagicMock()
        with patch("utils.tiktok_uploader._is_logged_in", return_value=False), \
             patch("utils.tiktok_uploader._do_login", return_value=False):
            result = tiktok_uploader._ensure_login(page, MagicMock(), "a@b.com", "pw", tmp_path / "s.json")
        assert result is False

    def test_returns_false_without_credentials_and_expired_session(self, tmp_path):
        """Contas que so logam via QR code/Google nao tem senha - sessao
        expirada sem credenciais de fallback e uma falha definitiva, e
        _do_login nao deve nem ser chamado (nao ha email/senha pra usar)."""
        page = MagicMock()
        with patch("utils.tiktok_uploader._is_logged_in", return_value=False), \
             patch("utils.tiktok_uploader._do_login") as mock_login:
            result = tiktok_uploader._ensure_login(page, MagicMock(), "", "", tmp_path / "s.json")
        assert result is False
        mock_login.assert_not_called()


class _FakePlaywrightCM:
    """Contexto `with sync_playwright() as p:` mockado: p.chromium.launch()
    retorna um browser cujo new_context()/new_page() sao configuraveis."""

    def __init__(self, browser):
        self._browser = browser

    def __enter__(self):
        p = MagicMock()
        p.chromium.launch.return_value = self._browser
        return p

    def __exit__(self, *a):
        return False


class TestUploadToTiktok:
    def _base_env(self, monkeypatch):
        monkeypatch.setenv("TIKTOK_EMAIL", "a@b.com")
        monkeypatch.setenv("TIKTOK_PASSWORD", "secret")

    def test_returns_none_without_credentials_or_session(self, monkeypatch, tmp_path):
        monkeypatch.delenv("TIKTOK_EMAIL", raising=False)
        monkeypatch.delenv("TIKTOK_PASSWORD", raising=False)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        result = tiktok_uploader.upload_to_tiktok(video, {}, state_path=tmp_path / "no_session.json")
        assert result is None

    def test_proceeds_with_existing_session_and_no_credentials(self, monkeypatch, tmp_path):
        """Contas que so logam via QR code/Google (sem senha) dependem
        exclusivamente de uma sessao salva (tiktok_state.json) - sem
        TIKTOK_EMAIL/TIKTOK_PASSWORD configurados, o upload ainda deve
        seguir em frente se ja existir uma sessao valida em disco."""
        monkeypatch.delenv("TIKTOK_EMAIL", raising=False)
        monkeypatch.delenv("TIKTOK_PASSWORD", raising=False)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        state_path = tmp_path / "state.json"
        state_path.write_text("{}")

        page = MagicMock()
        page.url = "https://www.tiktok.com/upload"
        avatar, file_input, desc_el, post_btn = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        page.query_selector.side_effect = [avatar, file_input, desc_el, post_btn]
        page.inner_text.return_value = ""

        def advance_after_post(*a, **k):
            page.url = "https://www.tiktok.com/@user/video/123"

        post_btn.click.side_effect = advance_after_post

        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context

        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        monkeypatch.setattr(tiktok_uploader, "_write_upload_state", lambda *a, **k: None)

        with patch("playwright.sync_api.sync_playwright", return_value=_FakePlaywrightCM(browser)):
            url = tiktok_uploader.upload_to_tiktok(
                video, {"title": "Cute cat", "hashtags": ["#Cats"]},
                state_path=state_path, headless=True,
            )

        assert url == "https://www.tiktok.com/@user/video/123"

    def test_returns_none_when_video_missing(self, monkeypatch, tmp_path):
        self._base_env(monkeypatch)
        assert tiktok_uploader.upload_to_tiktok(tmp_path / "missing.mp4", {}) is None

    def test_full_success_flow_returns_url(self, monkeypatch, tmp_path):
        self._base_env(monkeypatch)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        state_path = tmp_path / "state.json"

        page = MagicMock()
        page.url = "https://www.tiktok.com/upload"
        avatar, file_input, desc_el, post_btn = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        page.query_selector.side_effect = [avatar, file_input, desc_el, post_btn]
        page.inner_text.return_value = ""

        def advance_after_post(*a, **k):
            page.url = "https://www.tiktok.com/@user/video/123"

        post_btn.click.side_effect = advance_after_post

        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context

        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        monkeypatch.setattr(tiktok_uploader, "_write_upload_state", lambda *a, **k: None)

        with patch("playwright.sync_api.sync_playwright", return_value=_FakePlaywrightCM(browser)):
            url = tiktok_uploader.upload_to_tiktok(
                video, {"title": "Cute cat", "hashtags": ["#Cats"]},
                state_path=state_path, headless=True,
            )

        assert url == "https://www.tiktok.com/@user/video/123"
        browser.close.assert_called_once()

    def test_login_failure_returns_none_and_closes_browser(self, monkeypatch, tmp_path):
        self._base_env(monkeypatch)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")

        page = MagicMock()
        page.url = "https://www.tiktok.com/login/phone-or-email/email"
        page.query_selector.return_value = None  # sem avatar -> nao logado; sem campo email -> login falha
        page.inner_text.return_value = ""

        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context

        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        monkeypatch.setattr(tiktok_uploader, "_write_upload_state", lambda *a, **k: None)

        with patch("playwright.sync_api.sync_playwright", return_value=_FakePlaywrightCM(browser)):
            url = tiktok_uploader.upload_to_tiktok(video, {}, state_path=tmp_path / "s.json")

        assert url is None
        browser.close.assert_called_once()

    def test_post_processing_error_marker_aborts(self, monkeypatch, tmp_path):
        """Se um erro do TikTok aparece na tela enquanto aguarda o
        processamento do arquivo (antes mesmo de existir botao Post),
        aborta em vez de esperar os 240s inteiros."""
        self._base_env(monkeypatch)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")

        page = MagicMock()
        page.url = "https://www.tiktok.com/upload"
        page.query_selector.side_effect = [
            MagicMock(),  # avatar -> logado
            MagicMock(),  # file_input
            None, None,   # desc_el/post_btn ainda nao apareceram
        ]
        page.inner_text.return_value = "Upload failed, please try again"

        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context

        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        states: list[tuple] = []
        monkeypatch.setattr(tiktok_uploader, "_write_upload_state", lambda *a, **k: states.append(a))

        with patch("playwright.sync_api.sync_playwright", return_value=_FakePlaywrightCM(browser)):
            url = tiktok_uploader.upload_to_tiktok(video, {}, state_path=tmp_path / "s.json")

        assert url is None
        assert any(s[1] == "failed" for s in states)

    def test_corrupted_storage_state_falls_back_to_fresh_context(self, monkeypatch, tmp_path):
        """new_context() com storage_state corrompido levanta na primeira
        tentativa - deve descartar o arquivo e recriar o contexto sem
        storage_state em vez de derrubar o upload inteiro."""
        self._base_env(monkeypatch)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        state_path = tmp_path / "state.json"
        state_path.write_text("not valid json state")

        page = MagicMock()
        page.url = "https://www.tiktok.com/login/phone-or-email/email"
        page.query_selector.return_value = None
        page.inner_text.return_value = ""

        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.side_effect = [RuntimeError("invalid storageState"), context]

        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        monkeypatch.setattr(tiktok_uploader, "_write_upload_state", lambda *a, **k: None)

        with patch("playwright.sync_api.sync_playwright", return_value=_FakePlaywrightCM(browser)):
            tiktok_uploader.upload_to_tiktok(video, {}, state_path=state_path)

        assert browser.new_context.call_count == 2
        assert not state_path.exists()

    def test_exception_mid_flow_logs_to_file_and_returns_none(self, monkeypatch, tmp_path):
        self._base_env(monkeypatch)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")

        browser = MagicMock()
        browser.new_context.side_effect = RuntimeError("boom")

        monkeypatch.setattr(tiktok_uploader.time, "sleep", lambda *_: None)
        monkeypatch.setattr(tiktok_uploader, "_write_upload_state", lambda *a, **k: None)

        with patch("playwright.sync_api.sync_playwright", return_value=_FakePlaywrightCM(browser)), \
             patch("utils.log_config.log_exception_to_file") as mock_log_exc:
            url = tiktok_uploader.upload_to_tiktok(video, {}, state_path=tmp_path / "s.json")

        assert url is None
        mock_log_exc.assert_called_once()
        browser.close.assert_called_once()
