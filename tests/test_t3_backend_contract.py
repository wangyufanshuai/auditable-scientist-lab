import copy
import json
from pathlib import Path

import pytest

from scripts.verify_t3_backend_contract import _verify_entry, build_receipt


ROOT = Path(__file__).resolve().parents[1]


def test_t3_backend_contract_matches_saved_audit() -> None:
    saved = json.loads((ROOT / "artifacts/t3-backend-contract-audit.json").read_text(encoding="utf-8"))
    recorded_at = saved.pop("recorded_at")
    assert recorded_at.endswith("+00:00") or recorded_at.endswith("Z")
    assert saved == build_receipt()


@pytest.mark.parametrize("mutation", ["budget", "source", "boundary"])
def test_t3_backend_contract_rejects_mutation(mutation: str) -> None:
    contract = json.loads((ROOT / "docs/T3_BACKEND_CONTRACT.json").read_text(encoding="utf-8"))
    entry = copy.deepcopy(contract["audits"][0])
    artifact_path = ROOT / entry["artifact"]
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if mutation == "budget":
        artifact["observed_budget"]["dop853_rhs_calls_total"] = artifact["compute_budget"]["dop853_rhs_calls_total_max"] + 1
    elif mutation == "source":
        entry["required_source_paths"] = entry["required_source_paths"][:-1]
    else:
        artifact["scientific_boundaries"]["claim_status"] = "reproduced"
    original_load = __import__("scripts.verify_t3_backend_contract", fromlist=["_load"])._load
    module = __import__("scripts.verify_t3_backend_contract", fromlist=["_load"])
    module._load = lambda path: artifact if path == artifact_path else original_load(path)
    try:
        with pytest.raises(ValueError):
            _verify_entry(entry)
    finally:
        module._load = original_load
