"""The projectile source diagnostic blocks duplicate-trial holdout overclaims."""

from copy import deepcopy
import json

import pytest

from scripts import verify_t2_projectile_trial_independence as diagnostic


def test_saved_diagnostic_finds_cross_split_duplicate() -> None:
    result = diagnostic.verify_saved()
    assert result["status"] == "verified-posthoc-duplicate-trial-diagnostic-only"
    assert result["trial_count"] == 30
    assert result["sample_count"] == 179
    assert result["duplicate_groups"] == [
        {
            "trial_ids": [22, 23],
            "sample_count": 6,
            "signature_sha256": "14aade88751a370669a4cafe64ced4df89079226e1020df10f83cc204cf6de2c",
            "holdout_trial_ids": [22],
            "training_trial_ids": [23],
            "crosses_holdout_boundary": True,
        }
    ]
    assert result["boundaries"]["whole_trial_holdout_safe"] is False


def test_saved_diagnostic_rejects_tampering() -> None:
    saved = json.loads(diagnostic.AUDIT.read_text(encoding="utf-8"))
    changed = deepcopy(saved)
    changed["boundaries"]["whole_trial_holdout_safe"] = True
    with pytest.raises(ValueError, match="receipt differs"):
        diagnostic.verify_saved(changed)
