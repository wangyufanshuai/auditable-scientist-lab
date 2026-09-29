"""The wheel's bundled offline inputs must match checkout originals byte for byte."""

from pathlib import Path
from zipfile import ZipFile

from auditable_scientist.cli import _source_paths
from auditable_scientist.tracks.runner import track_source_paths


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DATA = ROOT / "src/auditable_scientist/_resources"


def test_bundled_offline_resources_match_checkout() -> None:
    expected = [
        ROOT / "pyproject.toml",
        *(ROOT / "schemas").glob("*.json"),
        ROOT / "docs/EVIDENCE_POLICY.md",
        ROOT / "docs/DECISIONS.md",
        ROOT / "docs/T1_SYMBOLIC_GRAMMAR.md",
        ROOT / "docs/T3_METHOD.md",
        ROOT / "docs/T3_CONVERGENCE_WHEEL.md",
        ROOT / "docs/T2_PHYSICAL_METHOD.md",
        ROOT / "docs/T3_NBODY_METHOD.md",
        ROOT / "docs/T4_METHOD.md",
        ROOT / "docs/T4_FLOATING_CONFORMANCE.md",
        ROOT / "docs/T5_METHOD.md",
        ROOT / "docs/T5_SOURCE_AVAILABILITY.md",
        *(ROOT / "examples").glob("*/*.json"),
    ]
    assert expected
    for source in expected:
        bundled = PACKAGE_DATA / source.relative_to(ROOT)
        assert bundled.is_file(), source
        assert bundled.read_bytes() == source.read_bytes(), source


def test_replayed_sources_use_stable_lf_bytes() -> None:
    paths = {
        *_source_paths(),
        *(path for track_id in ("T2", "T2P", "T3", "T3N", "T4", "T4O", "T5") for path in track_source_paths(track_id)),
        *(ROOT / "examples").glob("*/*.json"),
        *PACKAGE_DATA.rglob("*")
    }
    for path in paths:
        if path.is_file() and path.suffix != ".zip":
            assert bytes([13, 10]) not in path.read_bytes(), path
    bundle = PACKAGE_DATA / "legacy-runtime-8c26a26.zip"
    with ZipFile(bundle) as archive:
        for name in archive.namelist():
            assert bytes([13, 10]) not in archive.read(name), name
