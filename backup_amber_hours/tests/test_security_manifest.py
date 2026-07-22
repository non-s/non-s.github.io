from email.message import Message

from scripts.security_manifest import _license_from_metadata


def test_security_manifest_prefers_license_expression():
    meta = Message()
    meta["License"] = ""
    meta["License-Expression"] = "MIT-CMU"

    assert _license_from_metadata(meta) == "MIT-CMU"


def test_security_manifest_falls_back_to_osi_classifier():
    meta = Message()
    meta["Classifier"] = "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)"

    assert _license_from_metadata(meta) == "GNU Lesser General Public License v3 (LGPLv3)"
