"""DE440s source bytes and evidence level remain explicit and bounded."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from auditable_scientist.adapters.naif_de440s import compare_fixed_departures


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "artifacts/t1-de440s-ephemeris-snapshot.json"
KERNEL = ROOT / "data/naif/de440s.bsp"


def test_saved_ephemeris_snapshot_does_not_promote_mission() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "artifacts/t1-de440s-ephemeris-audit.json").read_text(encoding="utf-8"))
    assert snapshot["claim_status"] == "unverified"
    assert snapshot["evidence_level"] == "real-data"
    assert [row["departure_jd_tdb"] for row in snapshot["cases"]] == [2460584.5, 2461375.5]
    assert snapshot["coordinate_contract"]["mars_target"].startswith("MARS BARYCENTER")
    assert audit["boundaries"]["mission_trajectory_validated"] is False
    assert audit["boundaries"]["spacecraft_trajectory_propagated"] is False
    assert sha256(SNAPSHOT.read_bytes()).hexdigest() == audit["snapshot_sha256"]


def test_wrong_kernel_bytes_fail_before_spice_call(tmp_path: Path) -> None:
    fake = tmp_path / "de440s.bsp"
    fake.write_bytes(b"forged kernel")
    pytest.importorskip("spiceypy")
    with pytest.raises(ValueError, match="pinned NAIF source"):
        compare_fixed_departures(fake)


def test_optional_kernel_recomputes_exact_saved_snapshot() -> None:
    pytest.importorskip("spiceypy")
    if not KERNEL.is_file():
        pytest.skip("optional 31 MiB NAIF kernel is not in this checkout")
    result = compare_fixed_departures(KERNEL)
    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert result == saved
