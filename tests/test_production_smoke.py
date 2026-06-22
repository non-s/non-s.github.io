import urllib.error

from scripts.production_smoke import DEFAULT_URLS, SmokeResponse, normalize_url, run_smoke


def test_default_smoke_urls_include_public_security_contact():
    assert "https://non-s.github.io/.well-known/security.txt" in DEFAULT_URLS


def test_default_smoke_urls_include_public_discovery_and_404_pages():
    expected = {
        "https://non-s.github.io/404.html",
        "https://non-s.github.io/robots.txt",
        "https://non-s.github.io/sitemap.xml",
        "https://non-s.github.io/TakStud/404.html",
        "https://non-s.github.io/TakStud/robots.txt",
        "https://non-s.github.io/TakStud/sitemap.xml",
        "https://non-s.github.io/MathQuest-/404.html",
        "https://non-s.github.io/MathQuest-/robots.txt",
        "https://non-s.github.io/MathQuest-/sitemap.xml",
        "https://non-s.github.io/CHAMADA-/404.html",
        "https://non-s.github.io/CHAMADA-/robots.txt",
        "https://non-s.github.io/CHAMADA-/sitemap.xml",
        "https://non-s.github.io/Non-s/404.html",
        "https://non-s.github.io/Non-s/robots.txt",
        "https://non-s.github.io/Non-s/sitemap.xml",
        "https://non-s.github.io/Portfolio/404.html",
        "https://non-s.github.io/Portfolio/robots.txt",
        "https://non-s.github.io/Portfolio/sitemap.xml",
        "https://non-s.github.io/Uplift/404.html",
        "https://non-s.github.io/Uplift/robots.txt",
        "https://non-s.github.io/Uplift/sitemap.xml",
        "https://non-s.github.io/CLI-P2P/404.html",
        "https://non-s.github.io/CLI-P2P/robots.txt",
        "https://non-s.github.io/CLI-P2P/sitemap.xml",
    }

    assert expected.issubset(set(DEFAULT_URLS))


def test_production_smoke_allows_short_text_seed_urls():
    def fake_fetch(url: str, timeout: float) -> SmokeResponse:
        return SmokeResponse(url, 200, b"User-agent: *\nAllow: /\n", "text/plain", 12)

    results, failures = run_smoke(["https://non-s.github.io/robots.txt"], fetcher=fake_fetch)

    assert len(results) == 1
    assert failures == []


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
