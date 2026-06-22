from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_404_page_links_to_published_projects():
    html = (ROOT / "404.html").read_text(encoding="utf-8")

    assert "Pagina nao encontrada" in html
    for path in ("/", "/TakStud/", "/MathQuest-/", "/CHAMADA-/", "/Non-s/", "/Portfolio/", "/Uplift/", "/CLI-P2P/"):
        assert f'href="{path}"' in html


def test_robots_txt_points_to_public_sitemap_and_security_contact():
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")

    assert "User-agent: *" in robots
    assert "Allow: /" in robots
    assert "Sitemap: https://non-s.github.io/sitemap.xml" in robots
    assert "https://non-s.github.io/.well-known/security.txt" in robots


def test_sitemap_lists_public_entry_points():
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")

    for url in (
        "https://non-s.github.io/",
        "https://non-s.github.io/TakStud/",
        "https://non-s.github.io/MathQuest-/",
        "https://non-s.github.io/MathQuest-/teacher.html",
        "https://non-s.github.io/CHAMADA-/",
        "https://non-s.github.io/Non-s/",
        "https://non-s.github.io/Portfolio/",
        "https://non-s.github.io/Uplift/",
        "https://non-s.github.io/CLI-P2P/",
    ):
        assert f"<loc>{url}</loc>" in sitemap
