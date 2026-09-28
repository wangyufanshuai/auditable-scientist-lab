"""Fetch the optional unmodified NAIF MAR099s kernel outside the offline core."""

from __future__ import annotations

import argparse
from hashlib import md5, sha256
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/mar099s.bsp"
OFFICIAL_MD5 = "fd7302dfbaa0c63ce85b1e98923ee6a1"
EXPECTED_BYTES = 67_594_240
DEFAULT_PATH = ROOT / "data/naif/mar099s.bsp"


def fingerprint(path: Path) -> dict[str, str | int]:
    md = md5(usedforsecurity=False)
    sha = sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > EXPECTED_BYTES:
                raise ValueError("MAR099s exceeds the pinned byte count")
            md.update(chunk)
            sha.update(chunk)
    if size != EXPECTED_BYTES or md.hexdigest() != OFFICIAL_MD5:
        raise ValueError("MAR099s differs from the pinned NAIF checksum or byte count")
    return {"sha256": sha.hexdigest(), "md5": md.hexdigest(), "bytes": size}


def download(path: Path) -> dict[str, str | int]:
    if path.exists():
        return fingerprint(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="mar099s-", suffix=".part", dir=path.parent)
    partial = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            with urlopen(URL, timeout=120) as response:
                if response.status != 200:
                    raise OSError(f"NAIF returned HTTP {response.status}")
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > EXPECTED_BYTES:
                        raise ValueError("MAR099s exceeds the pinned byte budget")
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
    args = parser.parse_args()
    path = args.output.resolve()
    digest = fingerprint(path) if args.verify else download(path)
    print(json.dumps({"source": URL, "path": str(path), "version": "MAR099s",
                      "official_md5": OFFICIAL_MD5, **digest}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
