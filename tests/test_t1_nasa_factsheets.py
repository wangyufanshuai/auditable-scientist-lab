"""Bounded checks for the optional, offline NASA parameter sensitivity audit."""

import copy
import json

import pytest

from scripts.verify_t1_nasa_factsheets import AUDIT, SNAPSHOT, digest, extract_rows, verify_snapshot


def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _change_value(snapshot: dict, body: str, key: str, before: str, after: str) -> None:
    row = next(item for item in snapshot["sources"] if item["body"] == body)["rows"][key]
    assert before in row["raw_html"]
    row["raw_html"] = row["raw_html"].replace(before, after, 1)
    row["row_sha256"] = digest(row["raw_html"].encode("utf-8"))
    row["values"] = [after if item == before else item for item in row["values"]]


def test_committed_fact_sheet_rows_and_audit_recompute() -> None:
    snapshot = _snapshot()
    audit = verify_snapshot(snapshot)
    assert audit == json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["status"] == "verified-offline-snapshot-only"
    assert audit["source_rights_status"] == "unreviewed-page-specific"
    assert audit["offline_origin_authentication"] is False
    assert audit["real_data_claim"] is False
    assert audit["scientific_validation_claim"] is False
    assert 0 < audit["parameter_sensitivity_days"] < 0.02


def test_source_row_bytes_and_declared_values_are_bound() -> None:
    snapshot = _snapshot()
    tampered = copy.deepcopy(snapshot)
    tampered["sources"][1]["rows"]["semimajor_axis_million_km"]["values"][0] = "228.956"
    with pytest.raises(ValueError, match="row bytes or values"):
        verify_snapshot(tampered)


def test_rehashed_cross_page_earth_disagreement_is_rejected() -> None:
    snapshot = _snapshot()
    _change_value(snapshot, "mars", "semimajor_axis_million_km", "149.598", "149.599")
    with pytest.raises(ValueError, match="Earth columns differ"):
        verify_snapshot(snapshot)


def test_rehashed_period_outside_kepler_gate_is_rejected() -> None:
    snapshot = _snapshot()
    _change_value(snapshot, "mars", "sidereal_period_days", "686.980", "690.980")
    with pytest.raises(ValueError, match="Kepler check"):
        verify_snapshot(snapshot)


def test_rights_overclaim_is_rejected() -> None:
    snapshot = _snapshot()
    snapshot["sources"][0]["rights_status"] = "cleared"
    with pytest.raises(ValueError, match="rights"):
        verify_snapshot(snapshot)


def test_earth_extractor_rejects_duplicate_orbital_rows() -> None:
    line = "Semimajor axis (10<sup>6</sup> km) 149.598"
    page = f"<h3>Orbital parameters</h3><pre>{line}\n{line}\nSidereal orbit period (days) 365.256</pre>".encode()
    with pytest.raises(ValueError, match="exactly one orbital parameter row"):
        extract_rows(page, "earth")
