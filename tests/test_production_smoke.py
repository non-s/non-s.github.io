import urllib.error

from scripts.production_smoke import DEFAULT_URLS, SmokeResponse, normalize_url, run_smoke


def test_default_smoke_urls_include_public_security_contact():
    assert "https://non-s.github.io/.well-known/security.txt" in DEFAULT_URLS


def test_production_smoke_discovers_same_host_assets_and_blocks_404s():
    bodies = {
        "https://non-s.github.io/": b"""
        <html><head>
          <link rel="stylesheet" href="/assets/site.css">
          <script src="/app.js"></script>
        </head><body><a href="https://example.com/offsite">offsite</a></body></html>
        """,
        "https://non-s.github.io/assets/site.css": b"body { color: #111; }",
        "https://non-s.github.io/app.js": b"console.log('ok');",
    }

    def fake_fetch(url: str, timeout: float) -> SmokeResponse:
        return SmokeResponse(url, 200, bodies[url], "text/html", 12)

    results, failures = run_smoke(["https://non-s.github.io/"], fetcher=fake_fetch)

    assert failures == []
    assert {item.url for item in results} == set(bodies)
    assert {item.kind for item in results} == {"page", "asset"}


def test_production_smoke_reports_http_errors():
    def fake_fetch(url: str, timeout: float) -> SmokeResponse:
        raise urllib.error.HTTPError(url, 500, "server error", {}, None)

    results, failures = run_smoke(["https://non-s.github.io/"], fetcher=fake_fetch)

    assert results == []
    assert failures == ["https://non-s.github.io/ returned HTTP 500"]


def test_normalize_url_keeps_only_non_s_github_pages_assets():
    normalized = normalize_url("https://non-s.github.io/MathQuest-/", "script.js")

    assert normalized == "https://non-s.github.io/MathQuest-/script.js"
    assert normalize_url("https://non-s.github.io/", "mailto:test@example.com") is None
    assert normalize_url("https://non-s.github.io/", "https://example.com/app.js") is None
