import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_security_txt() -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for line in (ROOT / ".well-known/security.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, value = line.split(":", 1)
        fields.setdefault(name.strip(), []).append(value.strip())
    return fields


def test_security_txt_exposes_required_public_vulnerability_fields():
    fields = parse_security_txt()

    assert "Contact" in fields
    assert "Expires" in fields
    assert "Preferred-Languages" in fields
    assert "Canonical" in fields
    assert "Policy" in fields
    assert fields["Canonical"] == ["https://non-s.github.io/.well-known/security.txt"]
    assert fields["Policy"] == ["https://github.com/non-s/non-s.github.io/security/policy"]

    expires = datetime.fromisoformat(fields["Expires"][0].replace("Z", "+00:00"))
    assert expires > datetime.now(timezone.utc)


def test_jekyll_pages_config_publishes_well_known_directory():
    config = (ROOT / "_config.yml").read_text(encoding="utf-8")

    assert "include:" in config
    assert "- .well-known" in config


def test_dashboard_build_publishes_public_root_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(ROOT / "scripts"))
    (tmp_path / ".well-known").mkdir()
    source = (ROOT / ".well-known/security.txt").read_text(encoding="utf-8")
    (tmp_path / ".well-known/security.txt").write_text(source, encoding="utf-8")
    public_files = {
        "404.html": "<!doctype html><title>Not found</title>",
        "robots.txt": "User-agent: *\nAllow: /\n",
        "sitemap.xml": "<?xml version='1.0'?><urlset></urlset>",
    }
    for name, body in public_files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")

    if "build_dashboard" in sys.modules:
        del sys.modules["build_dashboard"]
    import build_dashboard

    importlib.reload(build_dashboard)
    build_dashboard.main()

    published = tmp_path / "_site/.well-known/security.txt"
    assert published.read_text(encoding="utf-8") == source
    for name, body in public_files.items():
        assert (tmp_path / "_site" / name).read_text(encoding="utf-8") == body
