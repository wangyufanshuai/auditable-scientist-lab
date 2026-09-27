"""Fetch the optional unmodified NAIF DE440s kernel outside the offline core."""

from __future__ import annotations

import argparse
from hashlib import md5, sha256
import json
from pathlib import Path
import tempfile
import os
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp"
OFFICIAL_MD5 = "3917ee56769db332790c751e2168843d"
DEFAULT_PATH = ROOT / "data/naif/de440s.bsp"
MAX_BYTES = 40_000_000


def fingerprint(path: Path) -> dict[str, str | int]:
    md5_hash = md5(usedforsecurity=False)
    sha256_hash = sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
    if md5_hash.hexdigest() != OFFICIAL_MD5 or not 20_000_000 < size < MAX_BYTES:
        raise ValueError("DE440s bytes differ from the NAIF checksum or expected size")
    return {"sha256": sha256_hash.hexdigest(), "md5": md5_hash.hexdigest(), "bytes": size}


def download(path: Path) -> dict[str, str | int]:
    if path.exists():
        return fingerprint(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="de440s-", suffix=".part", dir=path.parent)
    partial = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            with urlopen(URL, timeout=60) as response:
                if response.status != 200:
                    raise OSError(f"NAIF returned HTTP {response.status}")
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("NAIF kernel exceeds the configured byte budget")
                    temporary.write(chunk)
        digest = fingerprint(partial)
        if path.exists():
            raise FileExistsError(f"kernel appeared during download: {path}")
        partial.replace(path)
        return digest
    finally:
        if partial.exists():
            partial.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--verify", action="store_true", help="require an existing local kernel")
    arguments = parser.parse_args()
    path = arguments.output.resolve()
    digest = fingerprint(path) if arguments.verify else download(path)
    print(json.dumps({"source": URL, "path": str(path), "version": "DE440s",
                      "official_md5": OFFICIAL_MD5, **digest}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
