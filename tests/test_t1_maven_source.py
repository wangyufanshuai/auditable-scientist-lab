"""Mission-state source controls must not promote an exploratory sample."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts import verify_acceptance
from scripts.fetch_maven_cruise import fingerprint


ROOT = Path(__file__).resolve().parents[1]


def test_wrong_maven_bytes_rejected_before_spice(tmp_path: Path) -> None:
    fake = tmp_path / "maven_cru_rec_131118_140923_v1.bsp"
    fake.write_bytes(b"forged reconstructed orbit")
    with pytest.raises(ValueError, match="pinned PDS product"):
        fingerprint(fake)


def test_static_acceptance_rejects_promoted_mission_holdout(monkeypatch: pytest.MonkeyPatch) -> None:
    original_load = verify_acceptance.load

    def tampered_load(path: str) -> dict:
        value = original_load(path)
        if path == "artifacts/t1-maven-source-audit.json":
            value = copy.deepcopy(value)
            value["boundaries"]["scientific_holdout"] = True
        return value

    monkeypatch.setattr(verify_acceptance, "load", tampered_load)
    with pytest.raises(ValueError, match="MAVEN saved source"):
        verify_acceptance.verify_optional_t1_maven_source()
