"""Scientific intake must refuse fitting before any downstream side effects."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from auditable_scientist.track_registry import canonical_bytes
from auditable_scientist.tracks import measurement_admission as gate
from scripts import verify_t2_measurement_admission as verifier


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CODES = [
    "velocity-role-unresolved", "experiment-coverage-unaccounted",
    "duplicate-content-crosses-split", "source-use-rights-unresolved",
    "drag-constants-unreviewed", "prospective-split-not-registered",
    "protocol-explicitly-denies-fit",
]


@pytest.fixture
def evidence_root(tmp_path: Path) -> Path:
    required = {row["path"] for row in gate.bundled_policy()["inputs"]}
    for role in gate.bundled_policy()["receipt_identities"]:
        binding = next(row for row in gate.bundled_policy()["inputs"] if row["role"] == role)
        receipt = json.loads((ROOT / binding["path"]).read_text(encoding="utf-8"))
        required.update(row["path"] for row in receipt["source_files"])
    for relative in required:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


def test_denial_is_derived_from_inspectable_receipts() -> None:
    decision = gate.evaluate(ROOT)
    assert [reason["code"] for reason in decision["blocking_reasons"]] == EXPECTED_CODES
    reasons = {item["code"]: item for item in decision["blocking_reasons"]}
    assert reasons["experiment-coverage-unaccounted"]["details"] == {
        "reported_experiments": 82, "inventoried_trials": 30, "unaccounted_experiments": 52,
    }
    assert reasons["duplicate-content-crosses-split"]["details"]["duplicate_groups"] == [
        {"trial_ids": [22, 23], "crosses_holdout_boundary": True},
    ]
    assert reasons["velocity-role-unresolved"]["details"]["affected_trial_ids"] == list(range(2, 32))
    assert decision["raw_observations_opened"] is False
    assert decision["boundaries"] == gate.BOUNDARIES


def test_fit_callback_and_raw_observations_remain_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    original = Path.read_bytes

    def guarded_read(path: Path) -> bytes:
        assert path.suffix not in {".xlsx", ".pdf"}, "raw source must not be opened by the admission gate"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(gate.MeasurementAdmissionDenied) as denial:
        gate.guarded_fit(ROOT, lambda: calls.append("fit"))
    assert calls == []
    assert denial.value.decision["fit_invoked"] is False
    assert [item["code"] for item in denial.value.decision["blocking_reasons"]] == EXPECTED_CODES


@pytest.mark.parametrize("relative", [row["path"] for row in gate.bundled_policy()["inputs"]])
def test_missing_or_modified_input_never_invokes_fit(relative: str, evidence_root: Path) -> None:
    calls = []
    path = evidence_root / relative
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="fingerprint differs"):
        gate.guarded_fit(evidence_root, lambda: calls.append("fit"))
    assert calls == []
    path.unlink()
    with pytest.raises(ValueError, match="missing or unsafe"):
        gate.guarded_fit(evidence_root, lambda: calls.append("fit"))
    assert calls == []


@pytest.mark.parametrize("mutation", ["approval", "receipt-hash", "path", "identity", "missing", "unknown-flag"])
def test_caller_cannot_spoof_admission_policy(mutation: str) -> None:
    policy = gate.bundled_policy()
    if mutation == "approval":
        policy["fit_approval_supported"] = True
    elif mutation == "receipt-hash":
        policy["inputs"][0]["sha256"] = "0" * 64
    elif mutation == "path":
        policy["inputs"][0]["path"] = "docs/../outside.json"
    elif mutation == "identity":
        policy["dataset_id"] = "another-dataset"
    elif mutation == "missing":
        policy["inputs"].pop()
    else:
        policy["fit_allowed"] = True
    calls = []
    with pytest.raises((ValueError, gate.ValidationError)):
        gate.guarded_fit(ROOT, lambda: calls.append("fit"), policy=policy)
    assert calls == []


def test_saved_audit_recomputes_callback_refusal() -> None:
    audit = verifier.verify_saved()
    assert audit["fit_callback_not_invoked"] is True
    assert audit["raw_observations_not_opened"] is True
    assert len(audit["decision"]["blocking_reasons"]) == 7


@pytest.mark.parametrize("mutation", ["fit", "typed-fit", "drop-reason", "callback", "source"])
def test_saved_audit_rejects_promotions_and_tampering(mutation: str) -> None:
    audit = deepcopy(json.loads(verifier.AUDIT.read_text(encoding="utf-8")))
    if mutation == "fit":
        audit["boundaries"]["model_fit_admitted"] = True
    elif mutation == "typed-fit":
        audit["boundaries"]["model_fit_admitted"] = 0
    elif mutation == "drop-reason":
        audit["decision"]["blocking_reasons"].pop()
    elif mutation == "callback":
        audit["fit_callback_not_invoked"] = False
    else:
        audit["source_files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="audit differs"):
        verifier.verify_saved(audit)


def test_cli_separates_valid_denial_and_required_admission(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    command = [sys.executable, "-m", "auditable_scientist.tracks.measurement_admission", "--root", str(ROOT)]
    assessment = subprocess.run(command, env=environment, text=True, capture_output=True, check=False)
    required = subprocess.run([*command, "--require-admission"], env=environment,
                              text=True, capture_output=True, check=False)
    assert assessment.returncode == 0
    assert required.returncode == 3
    assert json.loads(assessment.stdout) == json.loads(required.stdout)
    assert json.loads(required.stdout)["status"] == "blocked-before-model-fit"
    invalid = subprocess.run(
        [sys.executable, "-m", "auditable_scientist.tracks.measurement_admission",
         "--root", str(tmp_path), "--require-admission"],
        env=environment, text=True, capture_output=True, check=False,
    )
    assert invalid.returncode == 1
    assert invalid.stdout == ""
    assert "evidence invalid" in invalid.stderr


def test_relocation_preserves_decision(evidence_root: Path) -> None:
    assert canonical_bytes(gate.evaluate(ROOT)) == canonical_bytes(gate.evaluate(evidence_root))
