from __future__ import annotations

import hashlib
from pathlib import Path


def calculate_file_hash(
    file_path: str | Path,
    algorithm: str = "sha256",
    chunk_size: int = 1024 * 1024,
) -> str:
    path = Path(file_path)
    h = hashlib.new(algorithm)

    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


# Backward-compatible alias
def calculate_sha256(file_path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    return calculate_file_hash(file_path, algorithm="sha256", chunk_size=chunk_size)
