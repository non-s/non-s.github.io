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
