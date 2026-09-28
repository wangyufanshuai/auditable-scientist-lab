"""Mars-center source correction remains a bounded ephemeris diagnostic."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from auditable_scientist.adapters.naif_mars_center import compare_fixed_departures_center


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "artifacts/t1-mars-center-ephemeris-snapshot.json"
AUDIT = ROOT / "artifacts/t1-mars-center-ephemeris-audit.json"
DE440S = ROOT / "data/naif/de440s.bsp"
MAR099S = ROOT / "data/naif/mar099s.bsp"


def test_saved_mars_center_snapshot_keeps_mission_unverified() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    earlier = json.loads((ROOT / "artifacts/t1-de440s-ephemeris-snapshot.json").read_text(encoding="utf-8"))
    assert sha256(SNAPSHOT.read_bytes()).hexdigest() == audit["snapshot_sha256"]
    assert snapshot["claim_status"] == "unverified"
    assert snapshot["evidence_level"] == "real-data"
    assert audit["boundaries"]["mars_center_state_available"] is True
    assert audit["boundaries"]["spacecraft_trajectory_propagated"] is False
    assert audit["boundaries"]["independent_planetary_ephemeris"] is False
    assert [row["earth_departure_state_km_kms"] for row in snapshot["cases"]] == [
        row["earth_departure_state_km_kms"] for row in earlier["cases"]
    ]
    assert all(row["center_barycenter_separation_m"] < 1 for row in snapshot["cases"])


def test_wrong_mar099s_bytes_fail_before_spice_call(tmp_path: Path) -> None:
    pytest.importorskip("spiceypy")
    if not DE440S.is_file():
        pytest.skip("optional DE440s kernel is not in this checkout")
    fake = tmp_path / "mar099s.bsp"
    fake.write_bytes(b"forged satellite kernel")
    with pytest.raises(ValueError, match="pinned NAIF source"):
        compare_fixed_departures_center(DE440S, fake)


def test_optional_kernels_recompute_saved_center_snapshot() -> None:
    pytest.importorskip("spiceypy")
    if not DE440S.is_file() or not MAR099S.is_file():
        pytest.skip("optional NAIF kernels are not in this checkout")
    result = compare_fixed_departures_center(DE440S, MAR099S)
    assert result == json.loads(SNAPSHOT.read_text(encoding="utf-8"))
