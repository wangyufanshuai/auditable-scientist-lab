"""Fetch the optional, checksum-pinned PDS MAVEN reconstructed cruise SPK."""

from __future__ import annotations

import argparse
from hashlib import md5, sha256
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
FILENAME = "maven_cru_rec_131118_140923_v1.bsp"
URL = ("https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/"
       f"spice_kernels/spk/{FILENAME}")
LABEL_URL = URL[:-4] + ".xml"
PRODUCT_LIDVID = "urn:nasa:pds:maven.spice:spice_kernels:spk_maven_cru_rec_131118_140923_v1.bsp::1.0"
OFFICIAL_MD5 = "8d7c55ef3bb935ad487c529f5be5343d"
PINNED_SHA256 = "07c76dfc2a1f66a54b4dd74105b2a5a70d72192813abee3659a74d4d21988dc5"
EXPECTED_BYTES = 4_797_440
DEFAULT_PATH = ROOT / "data/naif" / FILENAME


def fingerprint(path: Path) -> dict[str, str | int]:
    md = md5(usedforsecurity=False)
    sha = sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > EXPECTED_BYTES:
                raise ValueError("MAVEN SPK exceeds the pinned byte count")
            md.update(chunk)
            sha.update(chunk)
    if (size != EXPECTED_BYTES or md.hexdigest() != OFFICIAL_MD5
            or sha.hexdigest() != PINNED_SHA256):
        raise ValueError("MAVEN SPK differs from its pinned PDS product")
    return {"sha256": sha.hexdigest(), "md5": md.hexdigest(), "bytes": size}


def download(path: Path) -> dict[str, str | int]:
    if path.exists():
        return fingerprint(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="maven-cruise-", suffix=".part", dir=path.parent)
    partial = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            with urlopen(URL, timeout=120) as response:
                if response.status != 200:
                    raise OSError(f"PDS returned HTTP {response.status}")
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > EXPECTED_BYTES:
                        raise ValueError("MAVEN SPK exceeds the pinned byte budget")
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
    parser.add_argument("--verify", action="store_true", help="require an existing local SPK")
    args = parser.parse_args()
    path = args.output.resolve()
    digest = fingerprint(path) if args.verify else download(path)
    print(json.dumps({"source": URL, "label": LABEL_URL, "product_lidvid": PRODUCT_LIDVID,
                      "path": str(path), **digest}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
