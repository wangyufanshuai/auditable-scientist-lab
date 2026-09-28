"""Mutation checks for the optional T1 shared Run's saved evidence boundary."""

import copy

import pytest

from scripts import verify_acceptance


@pytest.mark.parametrize("mutation", ["rights-overclaim", "result-control", "policy-control", "replay-hash"])
def test_optional_t1_run_static_rejects_overclaims(monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    original_load = verify_acceptance.load
    altered = copy.deepcopy(original_load("artifacts/t1-external-run-audit.json"))
    if mutation == "rights-overclaim":
        altered["boundaries"]["real_data"] = True
    elif mutation == "result-control":
        altered["result_tamper_rejected"] = False
    elif mutation == "policy-control":
        altered["policy_denials"]["wrong_provider_rejected"] = False
    else:
        altered["replay"]["manifest_hash"] = "0" * 64

    def load(path: str) -> dict:
        return altered if path == "artifacts/t1-external-run-audit.json" else original_load(path)

    monkeypatch.setattr(verify_acceptance, "load", load)
    with pytest.raises(ValueError):
        verify_acceptance.verify_optional_t1_run_static()
