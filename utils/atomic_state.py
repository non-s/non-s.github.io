"""Atomic, versioned JSON state with explicit migrations and rollback copies."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from utils.state_lock import state_lock

Migration = Callable[[Any], Any]


def load_versioned(path: Path, current_version: int, migrations: dict[int, Migration], default: Any) -> Any:
    """Load an envelope and migrate its payload without silently overwriting it."""
    if not path.exists():
        return default
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "schema_version" not in raw or "data" not in raw:
        raise ValueError(f"unversioned state: {path}")
    version = int(raw["schema_version"])
    if version > current_version:
        raise ValueError(f"state schema {version} is newer than supported {current_version}: {path}")
    data = raw["data"]
    while version < current_version:
        migration = migrations.get(version)
        if migration is None:
            raise ValueError(f"missing migration {version}->{version + 1}: {path}")
        data = migration(data)
        version += 1
    return data


def save_versioned(path: Path, data: Any, schema_version: int, *, backup: bool = True) -> None:
    """Durably replace state; retain one pre-write copy for operational rollback."""
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"schema_version": schema_version, "data": data}
    encoded = json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with state_lock(path):
        if backup and path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
