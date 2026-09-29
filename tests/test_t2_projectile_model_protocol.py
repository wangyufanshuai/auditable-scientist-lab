"""The T2 model comparison remains blocked until source gates close."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_t2_projectile_model_protocol as protocol_module  # noqa: E402


def test_protocol_is_verified_only_as_a_blocked_design() -> None:
    result = protocol_module.evaluate()
    assert result["status"] == "verified-blocked-protocol-only"
    assert result["holdout_trial_count"] == 9
    assert result["training_trial_count"] == 21
    assert result["fit_permitted"] is False
    assert result["physical_model_validated"] is False
    assert result["causal_effect_identified"] is False


@pytest.mark.parametrize("mutation", [
    "admit_fit", "register_split", "claim_model", "claim_causal", "add_result",
    "admit_duplicate_holdout",
])
def test_protocol_rejects_overclaim_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutation: str,
) -> None:
    protocol = json.loads(protocol_module.PROTOCOL.read_text(encoding="utf-8"))
    if mutation == "admit_fit":
        protocol["models"]["no_drag"]["v0_input_mode"] = "measured"
    elif mutation == "register_split":
        protocol["split"]["split_registered"] = True
    elif mutation == "claim_model":
        protocol["gates"]["physical_model_validated"] = True
    elif mutation == "claim_causal":
        protocol["gates"]["causal_effect_identified"] = True
    elif mutation == "admit_duplicate_holdout":
        protocol["negative_controls"]["duplicate_trial_content_cross_split_rejected"] = False
    else:
        protocol["result_artifact"] = "artifacts/t2-projectile-model-audit.json"
    destination = tmp_path / "protocol.json"
    destination.write_text(json.dumps(protocol), encoding="utf-8")
    monkeypatch.setattr(protocol_module, "PROTOCOL", destination)
    with pytest.raises(ValueError):
        protocol_module.evaluate()
