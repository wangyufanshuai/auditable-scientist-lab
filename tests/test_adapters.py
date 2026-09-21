from __future__ import annotations

import pytest

from auditable_scientist.adapters import (
    AdapterBlocked,
    AdapterStatus,
    BlockedExternalSymbolicProvider,
    SymbolicProviderRequest,
    built_in_manifests,
    map_external_evidence,
    Project05Adapter,
)


def test_builtin_adapter_manifests_keep_missing_provider_blocked() -> None:
    manifests = built_in_manifests()
    by_id = {item.adapter_id: item for item in manifests}
    assert by_id["symbolic-physics-engine"].status is AdapterStatus.BLOCKED
    assert by_id["symbolic-physics-engine"].code_reuse_allowed is False
    assert all(item.read_only for item in manifests)


def test_blocked_symbolic_provider_fails_closed() -> None:
    manifest = next(item for item in built_in_manifests() if item.adapter_id == "symbolic-physics-engine")
    provider = BlockedExternalSymbolicProvider(manifest)
    request = SymbolicProviderRequest(
        request_id="req-1",
        variables=["r1", "r2", "mu"],
        units={"r1": "km", "r2": "km", "mu": "km^3/s^2"},
        target="time_of_flight_days",
        candidate_budget=5,
        seed=17,
    )
    with pytest.raises(AdapterBlocked, match="blocked"):
        provider.generate(request)


def test_external_evidence_mapping_is_contract_only() -> None:
    reference = map_external_evidence(
        evidence_id="ev-paper-1",
        adapter_id="paper2project",
        external_id="claim-42",
        source_revision="local-snapshot-2026-09-20",
        provenance_status="unverified",
        allowed_use=["evidence-id-reference"],
    )
    assert reference.external_id == "claim-42"
    assert reference.provenance_status == "unverified"


def test_external_evidence_mapping_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        map_external_evidence(
            evidence_id="ev-invalid",
            adapter_id="paper2project",
            external_id="claim-42",
            source_revision="unknown",
            provenance_status="real-data",
            allowed_use=["evidence-id-reference"],
        )


def test_project05_adapter_records_read_only_snapshot_without_copying_code() -> None:
    adapter = Project05Adapter()
    snapshot = adapter.snapshot()
    assert snapshot.status == "unverified"
    assert snapshot.license_status == "no root LICENSE confirmed"
    assert {item.relative_path for item in snapshot.files} == {
        "README.md",
        "references.md",
        "src/main.py",
        "data/mars_hohmann_summary.csv",
    }
    assert adapter.verify_snapshot(snapshot) is True
