from __future__ import annotations

import hashlib
from pathlib import Path


def calculate_sha256(file_path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    path = Path(file_path)
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()
